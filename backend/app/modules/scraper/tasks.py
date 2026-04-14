"""Celery tasks for discovery and scraping (v2 dim/fact tables)."""

import asyncio
import traceback
from datetime import datetime, timedelta, timezone
from uuid import UUID

import structlog
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import Settings
from app.database import sync_session_factory
from app.models.app_tables import ScrapeLog
from app.models.dimensions import DimMarketplace
from app.models.facts import FactListing
from app.modules.marketplaces.service import MarketplacePoolService
from app.modules.scraper.discovery import DiscoveryCrawler
from app.modules.scraper.scraper_pool import ScraperPool
from app.modules.scraper.service import GlobalScrapeService
from app.workers.celery_app import celery_app

slog = structlog.get_logger(__name__)


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


def _persist_technical_error_log(listing_id: UUID, tb: str) -> None:
    """Write scrape_logs row for unhandled task failure (separate sync session)."""
    db = sync_session_factory()
    try:
        listing = db.get(FactListing, listing_id)
        if not listing:
            slog.warning("technical_error_skip_no_listing", listing_id=str(listing_id))
            return
        entry = ScrapeLog(
            listing_id=listing.id,
            marketplace_id=listing.marketplace_id,
            status="technical_error",
            url=listing.external_url or "",
            error_message=tb[:20000],
            scraper_type="celery",
            error_category="technical",
        )
        db.add(entry)
        db.commit()
        slog.info("technical_error_logged", listing_id=str(listing_id))
    except Exception:
        slog.exception("technical_error_persist_failed", listing_id=str(listing_id))
        try:
            db.rollback()
        except Exception:
            pass
    finally:
        db.close()


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
                slog.info("discover_all_marketplaces", active_count=seen)
                crawler = DiscoveryCrawler(db, scraper_pool)
                for mp in marketplaces:
                    try:
                        res = await crawler.discover(mp)
                        if res.status in {"completed", "partial", "no_categories"}:
                            completed += 1
                        errors.extend(res.errors)
                    except Exception as exc:
                        slog.exception("discovery_failed", marketplace_id=str(mp.id), error=str(exc))
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
                    "products_new": res.persisted_listings,
                    "errors": res.errors,
                }
        finally:
            await engine.dispose()

    return _run_async(_do())


def _run_scrape_all_pool() -> dict:
    """Scrape stale pool listings using sync Session (avoids async greenlet in Celery workers)."""
    try:
        return _run_scrape_all_pool_impl()
    except Exception:
        tb = traceback.format_exc()
        slog.exception("scrape_all_pool_fatal", traceback=tb)
        return {
            "queued": 0,
            "scraped_ok": 0,
            "scraped_failed": 0,
            "error": "technical_error",
            "traceback": tb,
        }


def _run_scrape_all_pool_impl() -> dict:
    scraper_pool = ScraperPool()
    threshold = datetime.now(timezone.utc) - timedelta(hours=6)
    stale_ids: list[UUID] = []
    ok = 0
    failed = 0
    db = sync_session_factory()
    try:
        result = db.execute(
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
        slog.info("scrape_all_pool_products", eligible_listings=len(stale_ids))
        svc = GlobalScrapeService(db, scraper_pool)
        for lid in stale_ids:
            try:
                listing_row = db.get(FactListing, lid)
                url_hint = (listing_row.external_url if listing_row else "")[:160]
                slog.info("scrape_listing_start", listing_id=str(lid), url=url_hint)
                r = svc.scrape_product(lid)
                slog.info(
                    "scrape_listing_end",
                    listing_id=str(lid),
                    success=r.success,
                    err=(r.error or "")[:120],
                )
                if r.success:
                    ok += 1
                else:
                    failed += 1
            except Exception as exc:
                tb = traceback.format_exc()
                slog.exception("scrape_listing_failed", listing_id=str(lid), traceback=tb)
                slog.error(
                    "exception_before_technical_error_log",
                    listing_id=str(lid),
                    exc_type=exc.__class__.__name__,
                    exc_message=str(exc)[:2000],
                )
                try:
                    db.rollback()
                except Exception:
                    slog.exception("rollback_after_listing_failure", listing_id=str(lid))
                _persist_technical_error_log(lid, tb)
                failed += 1
    finally:
        db.close()

    slog.info(
        "scrape_all_pool_products_finished",
        eligible=len(stale_ids),
        ok=ok,
        failed=failed,
    )
    return {
        "queued": len(stale_ids),
        "scraped_ok": ok,
        "scraped_failed": failed,
    }


@celery_app.task(
    bind=True,
    name="scrape_all_pool_products",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 1},
    soft_time_limit=120,
    time_limit=150,
)
def scrape_all_pool_products(self):
    """Scrape stale pool listings (last_checked_at null or older than 6 hours)."""
    slog.info("scrape_all_pool_products_started", celery_id=self.request.id)
    return _run_scrape_all_pool()


@celery_app.task(
    name="scrape_pool_product",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 1},
    soft_time_limit=120,
    time_limit=150,
)
def scrape_pool_product(self, listing_id: str):
    """Scrape one FactListing by UUID."""

    try:
        return _scrape_pool_product_impl(listing_id)
    except Exception as exc:
        tb = traceback.format_exc()
        slog.exception("scrape_pool_product_fatal", listing_id=listing_id, traceback=tb)
        slog.error(
            "exception_before_technical_error_log",
            listing_id=listing_id,
            exc_type=exc.__class__.__name__,
            exc_message=str(exc)[:2000],
        )
        try:
            _persist_technical_error_log(UUID(str(listing_id)), tb)
        except Exception:
            slog.exception("scrape_pool_product_technical_log_failed", listing_id=listing_id)
        return {
            "success": False,
            "listing_id": listing_id,
            "error": "technical_error",
            "traceback": tb,
            "url": None,
        }


def _scrape_pool_product_impl(listing_id: str) -> dict:
    scraper_pool = ScraperPool()
    db = sync_session_factory()
    try:
        lid = UUID(str(listing_id))
        svc = GlobalScrapeService(db, scraper_pool)
        r = svc.scrape_product(lid)
        return {
            "success": r.success,
            "listing_id": listing_id,
            "error": r.error,
            "url": r.url,
        }
    finally:
        db.close()


@celery_app.task(name="check_pool_completeness")
def check_pool_completeness():
    """Count listings missing price or product image."""

    scraper_pool = ScraperPool()
    db = sync_session_factory()
    try:
        svc = GlobalScrapeService(db, scraper_pool)
        incomplete = svc.find_incomplete_products(limit=500)
        ids = [str(x) for x in incomplete[:50]]
        return {"checked": len(incomplete), "listing_ids": ids}
    finally:
        db.close()


