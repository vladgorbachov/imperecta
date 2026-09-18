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


async def _enumerate(marketplace_code: str, max_urls: int) -> dict:
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
        )
        # Coverage denominator (roadmap item 2): persist the product-like URL
        # count as a LOWER-BOUND catalog estimate — raised, never shrunk, so
        # a narrower rerun cannot damage the quota math.
        if result.product_like > 0:
            from app.modules.persist.meta_write import (
                build_dim_marketplace_fields,
                write_meta_async,
            )

            current = int(getattr(marketplace, "catalog_size_estimate", None) or 0)
            if result.product_like > current:
                await write_meta_async(
                    table="dim_marketplace",
                    operation="update",
                    fields=build_dim_marketplace_fields(
                        id=marketplace.id,
                        catalog_size_estimate=result.product_like,
                    ),
                    reject_source="sitemap_enumerate",
                )
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
    """Enumerate one shop's full catalog from its sitemap tree."""
    try:
        summary = _run_async(_enumerate(marketplace_code, max_urls))
        slog.info("sitemap_enumerate_task_done", **summary)
        return summary
    except Exception as exc:
        slog.error(
            "sitemap_enumerate_task_failed",
            marketplace_code=marketplace_code,
            error=str(exc)[:500],
        )
        capture_exception_if_initialized(exc)
        return {"status": f"error:{type(exc).__name__}", "code": marketplace_code}
