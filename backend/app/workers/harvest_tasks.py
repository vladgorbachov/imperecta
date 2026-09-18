"""List-page price harvesting tasks (SITEMAP_FIRST slice 2).

Fetch a category/list page once, extract dozens of (url, price) offers via
the Rust core, ingest them through the standard firewall path. Pattern-A
worker bridge for DB access.
"""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import Settings
from app.models.dimensions import DimMarketplace
from app.observability.sentry_init import capture_exception_if_initialized
from app.workers.celery_app import celery_app

slog = structlog.get_logger(__name__)

DEFAULT_PAGES_PER_RUN = 20


def _run_async(coro):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    with ThreadPoolExecutor(
        max_workers=1, thread_name_prefix="harvest-async-bridge"
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


def _ingest_offers_sync(offers: list[dict[str, Any]], marketplace_id) -> dict[str, int]:
    """Own sync session per page (thread-safe under asyncio.to_thread)."""
    from app.database import sync_session_factory
    from app.modules.ingestion.list_offers import ingest_list_offers

    db = sync_session_factory()
    try:
        return ingest_list_offers(db, offers=offers, marketplace_id=marketplace_id)
    finally:
        db.close()


async def _harvest(marketplace_code: str, limit: int) -> dict:
    try:
        import imperecta_core
    except ImportError:
        return {"status": "rust_core_unavailable", "code": marketplace_code}

    from app.modules.discovery import cursor_store
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
            category_urls = list(
                cursor_store.get_discovered_category_urls(marketplace) or []
            )
    finally:
        await engine.dispose()

    if not category_urls:
        return {
            "status": "no_category_urls",
            "code": marketplace_code,
            "hint": "run discovery first or pass URLs explicitly",
        }

    pool = ScraperPool()
    pages = 0
    totals = {
        "matched": 0,
        "saved": 0,
        "unknown": 0,
        "unpriced": 0,
        "suspicious": 0,
        "onboarded": 0,
        "empty_pages": 0,
    }
    marketplace_id = marketplace.id
    for url in category_urls[:limit]:
        fetch = await pool.fetch_listing_html(url)
        if not fetch.html:
            totals["empty_pages"] += 1
            continue
        offers = imperecta_core.extract_list_offers(fetch.html, url)
        pages += 1
        if not offers:
            totals["empty_pages"] += 1
            continue
        counters = await asyncio.to_thread(_ingest_offers_sync, offers, marketplace_id)
        for key in ("matched", "saved", "unknown", "unpriced", "suspicious", "onboarded"):
            totals[key] += counters.get(key, 0)

    return {
        "status": "completed",
        "code": marketplace_code,
        "pages_fetched": pages,
        **totals,
    }


# acks_late: a deploy's SIGTERM must not eat a queued/running harvest — the
# task is idempotent (no_change dedupe + url_hash onboarding dedupe), so a
# visibility-timeout redelivery after a worker death is safe and desired.
@celery_app.task(name="harvest_list_pages", bind=True, acks_late=True)
def harvest_list_pages(
    self,
    marketplace_code: str,
    limit: int = DEFAULT_PAGES_PER_RUN,
) -> dict:
    """Harvest prices from up to `limit` known category pages of one shop."""
    try:
        summary = _run_async(_harvest(marketplace_code, limit))
        slog.info("harvest_list_pages_done", **summary)
        return summary
    except Exception as exc:
        slog.error(
            "harvest_list_pages_failed",
            marketplace_code=marketplace_code,
            error=str(exc)[:500],
        )
        capture_exception_if_initialized(exc)
        return {"status": f"error:{type(exc).__name__}", "code": marketplace_code}
