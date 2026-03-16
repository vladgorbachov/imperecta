"""Celery tasks for discovery and global pool scraping."""

import asyncio
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import Settings
from app.models.admin_marketplace import AdminMarketplace
from app.scrapers.discovery_crawler import DiscoveryCrawler
from app.scrapers.scraper_pool import ScraperPool
from app.services.global_scrape_service import GlobalScrapeService
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def _run_async(coro):
    """Run async coroutine from sync Celery task."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
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
    """Beat: discover products for all active marketplaces. Every 24h."""

    async def _do() -> dict:
        engine, session_factory = _make_session_factory()
        try:
            async with session_factory() as db:
                result = await db.execute(
                    select(AdminMarketplace).where(AdminMarketplace.is_active.is_(True))
                )
                marketplaces = result.scalars().all()
                pool = ScraperPool()
                crawler = DiscoveryCrawler(db=db, scraper_pool=pool)
                summary = {"marketplaces": len(marketplaces), "completed": 0, "failed": 0}
                for marketplace in marketplaces:
                    discovery_result = await crawler.discover(marketplace)
                    if discovery_result.status in {"completed", "partial"}:
                        summary["completed"] += 1
                    else:
                        summary["failed"] += 1
                return summary
        finally:
            await engine.dispose()

    return _run_async(_do())


@celery_app.task(name="discover_single_marketplace", bind=True, max_retries=2)
def discover_single_marketplace(self, marketplace_id: int):
    """Discover for one marketplace."""

    async def _do() -> dict:
        engine, session_factory = _make_session_factory()
        try:
            async with session_factory() as db:
                marketplace = await db.get(AdminMarketplace, marketplace_id)
                if marketplace is None:
                    return {"status": "not_found", "marketplace_id": marketplace_id}
                pool = ScraperPool()
                crawler = DiscoveryCrawler(db=db, scraper_pool=pool)
                result = await crawler.discover(marketplace)
                return {
                    "status": result.status,
                    "marketplace_id": result.marketplace_id,
                    "products_new": result.products_new,
                    "products_found": result.products_found,
                    "pages_crawled": result.pages_crawled,
                }
        finally:
            await engine.dispose()

    try:
        return _run_async(_do())
    except Exception as exc:
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc)
        raise


@celery_app.task(name="scrape_all_pool_products")
def scrape_all_pool_products():
    """Beat: scrape stale products from global pool. Every 6h."""

    async def _do() -> dict:
        engine, session_factory = _make_session_factory()
        try:
            async with session_factory() as db:
                service = GlobalScrapeService(db=db, scraper_pool=ScraperPool())
                stale = await service.get_stale_products(limit=500)
                for product in stale:
                    await service.scrape_product(product.id)
                return {"queued": len(stale)}
        finally:
            await engine.dispose()

    return _run_async(_do())


@celery_app.task(name="scrape_pool_product", bind=True, max_retries=1)
def scrape_pool_product(self, product_id: int):
    """Scrape single product from pool."""

    async def _do() -> dict:
        engine, session_factory = _make_session_factory()
        try:
            async with session_factory() as db:
                service = GlobalScrapeService(db=db, scraper_pool=ScraperPool())
                result = await service.scrape_product(product_id)
                return {
                    "success": result.success,
                    "product_id": product_id,
                    "layer": result.scraper_layer,
                    "error": result.error,
                }
        finally:
            await engine.dispose()

    try:
        return _run_async(_do())
    except Exception as exc:
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc)
        raise


@celery_app.task(name="check_pool_completeness")
def check_pool_completeness():
    """Beat: find incomplete products, re-scrape them. Every 3h."""

    async def _do() -> dict:
        engine, session_factory = _make_session_factory()
        try:
            async with session_factory() as db:
                service = GlobalScrapeService(db=db, scraper_pool=ScraperPool())
                incomplete = await service.find_incomplete_products(limit=100)
                for product in incomplete:
                    await service.scrape_product(product.id)
                return {"checked": len(incomplete)}
        finally:
            await engine.dispose()

    return _run_async(_do())
