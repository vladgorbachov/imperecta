"""Celery tasks for discovery and scraping."""

import asyncio
import logging
import random
import time
from datetime import datetime, timezone
from uuid import UUID

from app.modules.alerts.tasks import check_alerts
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import joinedload

from app.config import Settings
from app.database import sync_session_factory
from app.models import AdminMarketplace, CompetitorProduct, PriceSnapshot
from app.modules.scraper.discovery import DiscoveryCrawler
from app.modules.scraper.engine import ScrapeResult
from app.modules.scraper.models import ScrapeLog
from app.modules.scraper.scraper_pool import ScraperPool
from app.modules.scraper.service import GlobalScrapeService, _detect_scraper_type, _get_scraper
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


def _update_admin_marketplace(db, marketplace_id: str, status: str, error_message: str | None) -> None:
    """Update AdminMarketplace stats if exists."""
    am = db.query(AdminMarketplace).filter(AdminMarketplace.marketplace_id == marketplace_id).first()
    if am:
        am.last_scrape_at = datetime.now(timezone.utc)
        am.last_scrape_status = status
        am.last_error = error_message
        am.total_scrapes += 1
        if status == "success":
            am.successful_scrapes += 1
        else:
            am.failed_scrapes += 1


@celery_app.task(name="discover_all_marketplaces")
def discover_all_marketplaces():
    """Beat: discover products for all active marketplaces. Every 24h."""

    async def _do() -> dict:
        from app.modules.marketplaces.service import MarketplacePoolService

        logger.info("=== Starting discover_all_marketplaces ===")
        engine, session_factory = _make_session_factory()
        try:
            async with session_factory() as db:
                # Recalculate quotas before discovery (fixes zero-quota when marketplaces added)
                svc = MarketplacePoolService(db)
                await svc.recalculate_all_quotas()
                logger.info("Quotas recalculated")

                result = await db.execute(
                    select(AdminMarketplace).where(AdminMarketplace.is_active.is_(True))
                )
                marketplaces = result.scalars().all()
                logger.info("Found %d active marketplaces", len(marketplaces))

                for mp in marketplaces:
                    logger.info(
                        "Marketplace %s: quota=%s, products_in_pool=%s, active=%s",
                        mp.domain,
                        mp.product_quota,
                        mp.products_in_pool,
                        mp.is_active,
                    )

                if not marketplaces:
                    logger.info("No active marketplaces, skipping discovery")
                    return {"marketplaces": 0, "completed": 0, "failed": 0}

                pool = ScraperPool()
                crawler = DiscoveryCrawler(db=db, scraper_pool=pool)
                summary = {"marketplaces": len(marketplaces), "completed": 0, "failed": 0}
                for marketplace in marketplaces:
                    discovery_result = await crawler.discover(marketplace)
                    logger.info(
                        "Discovery %s: status=%s, found=%d, new=%d",
                        marketplace.domain,
                        discovery_result.status,
                        discovery_result.products_found,
                        discovery_result.products_new,
                    )
                    if discovery_result.status in {"completed", "partial"}:
                        summary["completed"] += 1
                    else:
                        summary["failed"] += 1
                logger.info("=== Discovery completed: %s ===", summary)
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


@celery_app.task(
    name="scrape_single",
    bind=True,
    max_retries=2,
    default_retry_delay=30,
    soft_time_limit=120,
    time_limit=150,
)
def scrape_single(self, competitor_product_id: str):
    """Scrape a single competitor product URL."""
    start_time = time.time()

    with sync_session_factory() as db:
        cp = (
            db.query(CompetitorProduct)
            .options(joinedload(CompetitorProduct.competitor))
            .filter(
                CompetitorProduct.id == UUID(competitor_product_id),
                CompetitorProduct.is_active.is_(True),
            )
            .first()
        )

        if not cp:
            logger.warning("CompetitorProduct %s not found or inactive", competitor_product_id)
            return {"status": "skipped", "reason": "not found"}

        competitor = cp.competitor
        marketplace_id = competitor.marketplace if competitor else "unknown"
        marketplace_name = competitor.name if competitor else marketplace_id

        scraper_type = _detect_scraper_type(cp.url, cp.scraper_type)
        try:
            scraper = _get_scraper(scraper_type, cp.css_selector_price)
        except Exception as exc:
            logger.error("Failed to create scraper for type '%s': %s", scraper_type, exc)
            duration_ms = int((time.time() - start_time) * 1000)
            db.add(
                ScrapeLog(
                    marketplace_id=marketplace_id,
                    marketplace_name=marketplace_name,
                    competitor_product_id=cp.id,
                    url=cp.url,
                    status="error",
                    error_message=f"Scraper creation failed: {exc}",
                    duration_ms=duration_ms,
                )
            )
            _update_admin_marketplace(db, marketplace_id, "error", str(exc))
            db.commit()
            return {"status": "error", "error": str(exc)}

        try:
            result: ScrapeResult = asyncio.run(scraper.scrape(cp.url))
            duration_ms = int((time.time() - start_time) * 1000)
        except Exception as exc:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error("Scrape failed for %s: %s", cp.url[:80], exc)

            error_str = str(exc).lower()
            if "timeout" in error_str:
                status = "timeout"
            elif "403" in error_str or "blocked" in error_str or "captcha" in error_str:
                status = "blocked"
            else:
                status = "error"

            db.add(
                ScrapeLog(
                    marketplace_id=marketplace_id,
                    marketplace_name=marketplace_name,
                    competitor_product_id=cp.id,
                    url=cp.url,
                    status=status,
                    error_message=str(exc)[:2000],
                    duration_ms=duration_ms,
                    proxy_used=getattr(scraper.proxy_manager, "is_available", False),
                )
            )
            _update_admin_marketplace(db, marketplace_id, status, str(exc))
            db.commit()

            if status == "timeout" and self.request.retries < self.max_retries:
                raise self.retry(exc=exc)
            return {"status": status, "error": str(exc)}

        if result and result.price is not None and result.price > 0:
            old_price = cp.last_price
            old_in_stock = cp.last_in_stock

            snapshot = PriceSnapshot(
                competitor_product_id=cp.id,
                price=result.price,
                old_price=result.old_price,
                promo_label=result.promo_label,
                in_stock=result.in_stock if result.in_stock is not None else True,
            )
            db.add(snapshot)

            cp.last_price = result.price
            cp.last_promo_label = result.promo_label
            cp.last_in_stock = result.in_stock if result.in_stock is not None else True
            cp.last_checked_at = datetime.now(timezone.utc)
            if result.product_name and not cp.name:
                cp.name = result.product_name[:500]

            db.add(
                ScrapeLog(
                    marketplace_id=marketplace_id,
                    marketplace_name=marketplace_name,
                    competitor_product_id=cp.id,
                    url=cp.url,
                    status="success",
                    price_found=result.price,
                    duration_ms=duration_ms,
                    proxy_used=getattr(scraper.proxy_manager, "is_available", False),
                )
            )
            _update_admin_marketplace(db, marketplace_id, "success", None)
            db.commit()

            check_alerts.delay(
                competitor_product_id,
                str(old_price) if old_price is not None else None,
                str(result.price),
                result.promo_label or "",
                str(old_in_stock).lower() if old_in_stock is not None else None,
                str(result.in_stock).lower() if result.in_stock is not None else None,
            )

            return {"status": "success", "price": float(result.price), "url": cp.url}

        duration_ms = int((time.time() - start_time) * 1000)
        db.add(
            ScrapeLog(
                marketplace_id=marketplace_id,
                marketplace_name=marketplace_name,
                competitor_product_id=cp.id,
                url=cp.url,
                status="error",
                error_message="Price not found or zero",
                duration_ms=duration_ms,
            )
        )
        _update_admin_marketplace(db, marketplace_id, "error", "Price not found or zero")
        db.commit()
        return {"status": "error", "error": "Price not found"}


@celery_app.task(name="app.workers.scrape_tasks.scrape_user_products")
def scrape_user_products(user_id: str) -> None:
    """Get all active competitor_products for user, enqueue scrape_single with stagger."""
    with sync_session_factory() as db:
        from app.models import Product

        rows = (
            db.query(CompetitorProduct.id)
            .join(Product, CompetitorProduct.product_id == Product.id)
            .filter(
                Product.user_id == UUID(user_id),
                CompetitorProduct.is_active.is_(True),
            )
            .all()
        )
        ids = [str(row[0]) for row in rows]

    for index, cp_id in enumerate(ids):
        delay = random.uniform(2, 5) * index
        scrape_single.apply_async(args=[cp_id], countdown=delay)


@celery_app.task(name="scrape_all")
def scrape_all() -> dict:
    """Scrape ALL active competitor_products across ALL users."""
    with sync_session_factory() as db:
        active_cps = (
            db.query(CompetitorProduct.id)
            .filter(CompetitorProduct.is_active.is_(True))
            .all()
        )

    logger.info("Queuing scrape for %d competitor_products", len(active_cps))
    for (cp_id,) in active_cps:
        scrape_single.delay(str(cp_id))
    return {"queued": len(active_cps)}
