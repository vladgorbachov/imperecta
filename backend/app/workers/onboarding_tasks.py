"""Onboarding tasks: sitemap-full catalog enumeration (SITEMAP_FIRST slice 1).

DB access follows the Pattern-A worker bridge (see app.workers.reaper_tasks):
a fresh async engine per invocation, disposed before the loop closes — never
the module-level pool.
"""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import Settings
from app.models.dimensions import DimMarketplace
from app.modules.discovery.sitemap_enumerator import (
    ENUMERATE_MAX_URLS,
    enumerate_sitemap_full,
)
from app.observability.sentry_init import capture_exception_if_initialized
from app.workers.celery_app import celery_app

slog = structlog.get_logger(__name__)


def _run_async(coro):
    """Pattern-A bridge: safe asyncio.run from a sync Celery task."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    with ThreadPoolExecutor(
        max_workers=1, thread_name_prefix="onboarding-async-bridge"
    ) as executor:
        return executor.submit(asyncio.run, coro).result()


def _make_session_factory() -> tuple:
    settings = Settings()
    engine = create_async_engine(
        str(settings.database_url),
        pool_size=2,
        max_overflow=0,
        pool_pre_ping=True,
        connect_args={"statement_cache_size": 0},
    )
    factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )
    return engine, factory


# Fan-out: shards of this many first-level sub-sitemaps per child task.
# 300k-URL shops stop monopolizing one worker child for hours — up to
# worker_concurrency children chew the same shop's subtree in parallel
# (url_hash dedupe makes overlaps and redeliveries harmless).
ENUMERATE_SHARD_SUBFILES = 3
_ENUM_RUN_TTL_SEC = 24 * 3600


async def _load_marketplace(marketplace_code: str):
    engine, factory = _make_session_factory()
    try:
        async with factory() as db:
            return (
                await db.execute(
                    select(DimMarketplace).where(
                        DimMarketplace.marketplace_code == marketplace_code
                    )
                )
            ).scalar_one_or_none()
    finally:
        await engine.dispose()


async def _resolve_shards(marketplace_code: str) -> tuple[object, list[str]]:
    from app.modules.scraper.scraper_pool import ScraperPool

    engine, factory = _make_session_factory()
    try:
        async with factory() as db:
            marketplace = (
                await db.execute(
                    select(DimMarketplace).where(
                        DimMarketplace.marketplace_code == marketplace_code
                    )
                )
            ).scalar_one_or_none()
        if marketplace is None:
            return None, []
        resolved = await ScraperPool().resolve_sitemap_shards(marketplace.base_url)
        return marketplace, list(resolved.get("shards") or [])
    finally:
        await engine.dispose()


def _enum_run_keys(marketplace_code: str, run_id: str) -> tuple[str, str]:
    base = f"enumrun:{marketplace_code}:{run_id}"
    return f"{base}:pending", f"{base}:counts"


def _record_shard_done(
    marketplace_code: str, run_id: str, shard_no: int, product_like: int
) -> int | None:
    """Idempotently record a shard result; return the run total when this
    was the LAST shard, else None. Redis-lost degrades to per-shard None
    (the estimate then simply stays a lower bound from earlier data)."""
    from app.modules.scraper.pipeline.worker_log_relay import _get_redis

    try:
        client = _get_redis()
        pending_key, counts_key = _enum_run_keys(marketplace_code, run_id)
        # HSET is idempotent per shard (acks_late redelivery safe).
        client.hset(counts_key, str(shard_no), int(product_like))
        client.expire(counts_key, _ENUM_RUN_TTL_SEC)
        remaining = client.decr(pending_key)
        if remaining > 0:
            return None
        values = client.hvals(counts_key)
        return sum(int(v) for v in values)
    except Exception:
        return None


async def _write_estimate(marketplace, product_like_total: int) -> None:
    if product_like_total <= 0:
        return
    from app.modules.persist.meta_write import (
        build_dim_marketplace_fields,
        write_meta_async,
    )

    current = int(getattr(marketplace, "catalog_size_estimate", None) or 0)
    if product_like_total > current:
        await write_meta_async(
            table="dim_marketplace",
            operation="update",
            fields=build_dim_marketplace_fields(
                id=marketplace.id,
                catalog_size_estimate=product_like_total,
            ),
            reject_source="sitemap_enumerate",
        )


async def _enumerate(
    marketplace_code: str,
    max_urls: int,
    *,
    explicit_sitemaps: list[str] | None = None,
    write_estimate: bool = True,
) -> dict:
    from app.modules.scraper.scraper_pool import ScraperPool

    engine, factory = _make_session_factory()
    try:
        async with factory() as db:
            marketplace = (
                await db.execute(
                    select(DimMarketplace).where(
                        DimMarketplace.marketplace_code == marketplace_code
                    )
                )
            ).scalar_one_or_none()
            if marketplace is None:
                return {"status": "unknown_marketplace", "code": marketplace_code}
        # Enumeration itself needs no open async session: sitemap fetches go
        # through ScraperPool and persistence runs on short-lived sync
        # sessions in threads (gate path).
        result = await enumerate_sitemap_full(
            marketplace,
            ScraperPool(),
            max_urls=max_urls,
            explicit_sitemaps=explicit_sitemaps,
        )
        # Coverage denominator (roadmap item 2): persist the product-like URL
        # count as a LOWER-BOUND catalog estimate — raised, never shrunk, so
        # a narrower rerun cannot damage the quota math. Fan-out shards skip
        # this: the LAST shard aggregates the run total instead.
        if write_estimate:
            await _write_estimate(marketplace, result.product_like)
        return asdict(result)
    finally:
        await engine.dispose()


# acks_late: a deploy's SIGTERM must not eat a queued/running enumeration —
# url_hash dedupe makes reruns idempotent, so a visibility-timeout redelivery
# after a worker death only picks up what the dead run missed.
@celery_app.task(name="sitemap_enumerate_marketplace", bind=True, acks_late=True)
def sitemap_enumerate_marketplace(
    self,
    marketplace_code: str,
    max_urls: int = ENUMERATE_MAX_URLS,
) -> dict:
    """Enumerate one shop's catalog — coordinator with sub-sitemap fan-out.

    Shops whose sitemap index carries 2+ sub-sitemaps get sharded into
    child tasks (ENUMERATE_SHARD_SUBFILES roots each) so several worker
    children enumerate the shop in parallel; the flat-sitemap fallback
    runs inline exactly as before.
    """
    try:
        marketplace, shards = _run_async(_resolve_shards(marketplace_code))
        if marketplace is None:
            return {"status": "unknown_marketplace", "code": marketplace_code}
        if len(shards) < 2:
            summary = _run_async(_enumerate(marketplace_code, max_urls))
            slog.info("sitemap_enumerate_task_done", **summary)
            return summary

        import uuid as _uuid

        from app.modules.scraper.pipeline.worker_log_relay import _get_redis

        chunks = [
            shards[i : i + ENUMERATE_SHARD_SUBFILES]
            for i in range(0, len(shards), ENUMERATE_SHARD_SUBFILES)
        ]
        run_id = _uuid.uuid4().hex[:12]
        try:
            pending_key, _ = _enum_run_keys(marketplace_code, run_id)
            client = _get_redis()
            client.set(pending_key, len(chunks), ex=_ENUM_RUN_TTL_SEC)
        except Exception:
            pass
        per_shard_urls = max(max_urls // max(len(chunks), 1), 10_000)
        for shard_no, chunk in enumerate(chunks):
            sitemap_enumerate_shard.apply_async(
                [marketplace_code, chunk],
                kwargs={
                    "max_urls": per_shard_urls,
                    "run_id": run_id,
                    "shard_no": shard_no,
                },
                priority=8,
            )
        summary = {
            "status": "sharded",
            "code": marketplace_code,
            "shards": len(chunks),
            "subfiles": len(shards),
            "run_id": run_id,
        }
        slog.info("sitemap_enumerate_sharded", **summary)
        return summary
    except Exception as exc:
        slog.error(
            "sitemap_enumerate_task_failed",
            marketplace_code=marketplace_code,
            error=str(exc)[:500],
        )
        capture_exception_if_initialized(exc)
        return {"status": f"error:{type(exc).__name__}", "code": marketplace_code}


@celery_app.task(name="sitemap_enumerate_shard", bind=True, acks_late=True)
def sitemap_enumerate_shard(
    self,
    marketplace_code: str,
    shard_sitemaps: list[str],
    max_urls: int = ENUMERATE_MAX_URLS,
    run_id: str | None = None,
    shard_no: int = 0,
) -> dict:
    """Enumerate ONE shard (subset of sub-sitemaps) of a shop's tree."""
    try:
        summary = _run_async(
            _enumerate(
                marketplace_code,
                max_urls,
                explicit_sitemaps=shard_sitemaps,
                write_estimate=False,
            )
        )
        if run_id is not None:
            total = _record_shard_done(
                marketplace_code, run_id, shard_no, summary.get("product_like", 0)
            )
            if total is not None:
                marketplace = _run_async(_load_marketplace(marketplace_code))
                if marketplace is not None:
                    _run_async(_write_estimate(marketplace, total))
                summary["run_total_product_like"] = total
        slog.info("sitemap_enumerate_shard_done", shard=shard_no, **summary)
        return summary
    except Exception as exc:
        slog.error(
            "sitemap_enumerate_shard_failed",
            marketplace_code=marketplace_code,
            shard=shard_no,
            error=str(exc)[:500],
        )
        capture_exception_if_initialized(exc)
        return {"status": f"error:{type(exc).__name__}", "code": marketplace_code}
