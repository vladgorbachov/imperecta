"""Celery tasks for discovery and scraping (v2 dim/fact tables)."""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import Settings
from app.models.dimensions import DimMarketplace
from app.models.facts import FactListing
from app.modules.marketplaces.service import MarketplacePoolService
from app.modules.scraper.discovery import DiscoveryCrawler
from app.modules.scraper.scraper_pool import ScraperPool
from app.modules.scraper.service import GlobalScrapeService
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def _run_async(coro):
    """Run async coroutine from sync Celery task."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        try:
            loop.run_until_complete(loop.shutdown_asyncgens())
        except Exception:
            pass
        loop.close()


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


@celery_app.task(name="discover_all_marketplaces")
def discover_all_marketplaces():
    """Run discovery for each active DimMarketplace."""

    async def _do() -> dict:
        engine, session_factory = _make_session_factory()
        scraper_pool = ScraperPool()
        seen = 0
        completed = 0
        errors: list[str] = []
        try:
            async with session_factory() as db:
                await MarketplacePoolService(db).recalculate_all_quotas()
                result = await db.execute(
                    select(DimMarketplace)
                    .where(DimMarketplace.is_active.is_(True))
                    .order_by(DimMarketplace.marketplace_code),
                )
                marketplaces = list(result.scalars().all())
                seen = len(marketplaces)
                logger.info("discover_all_marketplaces: %d active marketplaces", seen)
                crawler = DiscoveryCrawler(db, scraper_pool)
                for mp in marketplaces:
                    try:
                        res = await crawler.discover(mp)
                        if res.status == "completed":
                            completed += 1
                        errors.extend(res.errors)
                    except Exception as exc:
                        logger.exception("Discovery failed for %s: %s", mp.id, exc)
                        errors.append(str(exc))
        finally:
            await engine.dispose()

        return {
            "dispatched": completed,
            "marketplaces_seen": seen,
            "errors": errors[:20],
        }

    return _run_async(_do())


@celery_app.task(
    name="discover_single_marketplace",
    bind=True,
    max_retries=2,
    soft_time_limit=300,
    time_limit=360,
)
def discover_single_marketplace(self, marketplace_id: str):
    """Run discovery for one marketplace (UUID string)."""

    async def _do() -> dict:
        engine, session_factory = _make_session_factory()
        scraper_pool = ScraperPool()
        try:
            async with session_factory() as db:
                mp_uuid = UUID(str(marketplace_id))
                marketplace = await db.get(DimMarketplace, mp_uuid)
                if not marketplace:
                    return {"status": "not_found", "marketplace_id": marketplace_id}
                crawler = DiscoveryCrawler(db, scraper_pool)
                res = await crawler.discover(marketplace)
                return {
                    "status": res.status,
                    "marketplace_id": str(marketplace.id),
                    "products_new": res.products_new,
                    "errors": res.errors,
                }
        finally:
            await engine.dispose()

    return _run_async(_do())


async def _run_scrape_all_pool() -> dict:
    """Scrape stale pool listings (last_checked_at null or older than 6 hours)."""
    engine, session_factory = _make_session_factory()
    scraper_pool = ScraperPool()
    threshold = datetime.now(timezone.utc) - timedelta(hours=6)
    stale_ids: list[UUID] = []
    ok = 0
    failed = 0
    try:
        async with session_factory() as db:
            result = await db.execute(
                select(FactListing.id)
                .where(FactListing.is_active.is_(True))
                .where(
                    or_(
                        FactListing.last_checked_at.is_(None),
                        FactListing.last_checked_at < threshold,
                    ),
                )
                .limit(500),
            )
            stale_ids = [r[0] for r in result.all()]
            svc = GlobalScrapeService(db, scraper_pool)
            for lid in stale_ids:
                try:
                    r = await svc.scrape_product(lid)
                    if r.success:
                        ok += 1
                    else:
                        failed += 1
                except Exception:
                    logger.exception("scrape listing %s", lid)
                    failed += 1
    finally:
        await engine.dispose()

    return {
        "queued": len(stale_ids),
        "scraped_ok": ok,
        "scraped_failed": failed,
    }


@celery_app.task(name="scrape_all_pool_products")
def scrape_all_pool_products():
    """Scrape stale pool listings (last_checked_at null or older than 6 hours)."""
    return _run_async(_run_scrape_all_pool())


@celery_app.task(
    name="scrape_pool_product",
    bind=True,
    max_retries=1,
    soft_time_limit=120,
    time_limit=150,
)
def scrape_pool_product(self, listing_id: str):
    """Scrape one FactListing by UUID."""

    async def _do() -> dict:
        engine, session_factory = _make_session_factory()
        scraper_pool = ScraperPool()
        try:
            async with session_factory() as db:
                lid = UUID(str(listing_id))
                svc = GlobalScrapeService(db, scraper_pool)
                r = await svc.scrape_product(lid)
                return {
                    "success": r.success,
                    "listing_id": listing_id,
                    "error": r.error,
                    "url": r.url,
                }
        finally:
            await engine.dispose()

    return _run_async(_do())


@celery_app.task(name="check_pool_completeness")
def check_pool_completeness():
    """Count listings missing price or product image."""

    async def _do() -> dict:
        engine, session_factory = _make_session_factory()
        scraper_pool = ScraperPool()
        try:
            async with session_factory() as db:
                svc = GlobalScrapeService(db, scraper_pool)
                incomplete = await svc.find_incomplete_products(limit=500)
                return {"checked": len(incomplete), "listing_ids": [str(x) for x in incomplete[:50]]}
        finally:
            await engine.dispose()

    return _run_async(_do())


@celery_app.task(
    name="scrape_single",
    bind=True,
    max_retries=2,
)
def scrape_single(self, competitor_product_id: str):
    """Legacy competitor scrape removed — use scrape_pool_product(listing_id)."""
    logger.warning("scrape_single is deprecated; use scrape_pool_product: %s", competitor_product_id)
    return {"status": "deprecated", "message": "Use scrape_pool_product with fact_listing UUID"}


@celery_app.task(name="app.workers.scrape_tasks.scrape_user_products")
def scrape_user_products(user_id: str) -> None:
    """Enqueue pool scrape for listings linked to user products (future)."""
    logger.info("scrape_user_products(%s): delegating to pool scrape task", user_id)
    scrape_all_pool_products.delay()


@celery_app.task(name="scrape_all")
def scrape_all() -> dict:
    """Alias: scrape stale pool listings (same logic as scrape_all_pool_products)."""
    return _run_async(_run_scrape_all_pool())
