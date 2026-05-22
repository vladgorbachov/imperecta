"""Celery tasks for discovery and scraping (v2 dim/fact tables)."""

import asyncio
import time
import traceback
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import Settings
from app.database import sync_session_factory
from app.models.app_tables import ScrapeJob, ScrapeLog
from app.models.dimensions import DimMarketplace
from app.models.facts import FactListing
from app.modules.marketplaces.service import MarketplacePoolService
from app.modules.admin.parsing_admin import ParsingAdminService
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


def _persist_technical_error_log(
    listing_id: UUID,
    tb: str,
    scrape_job_id: UUID | None = None,
) -> None:
    """Write scrape_logs row for unhandled task failure (separate sync session)."""
    db = sync_session_factory()
    try:
        listing = db.get(FactListing, listing_id)
        if not listing:
            slog.warning("technical_error_skip_no_listing", listing_id=str(listing_id))
            return
        entry = ScrapeLog(
            scrape_job_id=scrape_job_id,
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


def _run_scrape_all_pool(scrape_job_id: UUID | None = None) -> dict:
    """Scrape stale pool listings using sync Session (avoids async greenlet in Celery workers)."""
    try:
        return _run_scrape_all_pool_impl(scrape_job_id=scrape_job_id)
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


def _run_scrape_all_pool_impl(scrape_job_id: UUID | None = None) -> dict:
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
        svc = GlobalScrapeService(db, scraper_pool, scrape_job_id=scrape_job_id)
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
                _persist_technical_error_log(lid, tb, scrape_job_id=scrape_job_id)
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


def _extract_pipeline_metadata(config: Any) -> dict[str, Any]:
    if not isinstance(config, dict):
        return ParsingAdminService._build_initial_metadata()
    metadata = config.get("metadata")
    if isinstance(metadata, dict):
        return metadata
    return ParsingAdminService._build_initial_metadata()


async def _set_pipeline_stage(
    db: AsyncSession,
    job: ScrapeJob,
    stage: str,
) -> None:
    metadata = _extract_pipeline_metadata(job.config)
    metadata["current_stage"] = stage
    job.config = {"metadata": metadata}
    await db.commit()


async def _discover_for_full_pipeline(
    db: AsyncSession,
) -> tuple[int, dict[UUID, dict[str, Any]], list[str]]:
    domains = [seed.domain for seed in ParsingAdminService.TEST_MARKETPLACES]
    result = await db.execute(
        select(DimMarketplace)
        .where(DimMarketplace.is_active.is_(True), DimMarketplace.domain.in_(domains))
        .order_by(DimMarketplace.marketplace_code.asc())
    )
    marketplaces = list(result.scalars().all())
    crawler = DiscoveryCrawler(db, ScraperPool())
    errors: list[str] = []
    per_marketplace: dict[UUID, dict[str, Any]] = {}
    for marketplace in marketplaces:
        try:
            discovered = await crawler.discover(marketplace)
            per_marketplace[marketplace.id] = {
                "marketplace_id": str(marketplace.id),
                "domain": marketplace.domain,
                "listings_created": int(discovered.persisted_listings),
                "prices_saved": 0,
                "errors_count": int(len(discovered.errors)),
                "duration_ms": int(
                    (discovered.completed_at - discovered.started_at).total_seconds() * 1000
                )
                if discovered.completed_at
                else 0,
                "status": "failed" if discovered.status == "error" else "completed",
            }
            errors.extend(discovered.errors)
        except Exception as exc:
            slog.exception(
                "full_pipeline_discovery_failed",
                marketplace_id=str(marketplace.id),
                error=str(exc),
            )
            errors.append(str(exc))
            per_marketplace[marketplace.id] = {
                "marketplace_id": str(marketplace.id),
                "domain": marketplace.domain,
                "listings_created": 0,
                "prices_saved": 0,
                "errors_count": 1,
                "duration_ms": 0,
                "status": "failed",
            }
    return len(marketplaces), per_marketplace, errors


async def _finalize_full_pipeline_job(
    db: AsyncSession,
    job: ScrapeJob,
    *,
    discovery_ms: int,
    scrape_ms: int,
    persist_ms: int,
    per_marketplace_seed: dict[UUID, dict[str, Any]],
    hard_error: str | None = None,
) -> dict[str, Any]:
    log_stats = await db.execute(
        select(
            ScrapeLog.marketplace_id,
            func.sum(case((ScrapeLog.status == "success", 1), else_=0)).label("prices_saved"),
            func.sum(case((ScrapeLog.status != "success", 1), else_=0)).label("errors_count"),
        )
        .where(ScrapeLog.scrape_job_id == job.id)
        .group_by(ScrapeLog.marketplace_id)
    )

    stats_by_marketplace = {
        row.marketplace_id: {
            "prices_saved": int(row.prices_saved or 0),
            "errors_count": int(row.errors_count or 0),
        }
        for row in log_stats
    }

    merged: list[dict[str, Any]] = []
    for marketplace_id, seed in per_marketplace_seed.items():
        merged_entry = dict(seed)
        stats = stats_by_marketplace.get(marketplace_id, {})
        merged_entry["prices_saved"] = int(stats.get("prices_saved", merged_entry["prices_saved"]))
        merged_entry["errors_count"] = int(
            merged_entry["errors_count"] + stats.get("errors_count", 0)
        )
        if merged_entry["errors_count"] > 0 and merged_entry["status"] != "running":
            merged_entry["status"] = "failed"
        merged.append(merged_entry)

    listings_created = int(sum(item["listings_created"] for item in merged))
    prices_saved = int(sum(item["prices_saved"] for item in merged))
    errors_count = int(sum(item["errors_count"] for item in merged))
    total_ms = int(discovery_ms + scrape_ms + persist_ms)

    metadata = _extract_pipeline_metadata(job.config)
    metadata.update(
        {
            "current_stage": "failed" if hard_error else "completed",
            "timings": {
                "discovery_ms": int(discovery_ms),
                "scrape_ms": int(scrape_ms),
                "persist_ms": int(persist_ms),
                "total_ms": int(total_ms),
            },
            "summary": {
                "listings_created": listings_created,
                "prices_saved": prices_saved,
                "errors_count": errors_count,
            },
            "per_marketplace": merged,
        }
    )
    if hard_error:
        metadata["error"] = hard_error[:2000]

    completed_at = datetime.now(timezone.utc)
    job.completed_at = completed_at
    job.duration_ms = total_ms
    job.total_listings = listings_created
    job.successful = prices_saved
    job.failed = errors_count
    job.status = "failed" if hard_error else "completed"
    job.config = {"metadata": metadata}
    await db.commit()
    return metadata


@celery_app.task(
    bind=True,
    name="run_full_pipeline_test",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 1},
)
def run_full_pipeline_test(self, parent_job_id: str) -> dict:
    """Run discovery + scrape pipeline for parsing admin test flow."""

    async def _do() -> dict:
        engine, session_factory = _make_session_factory()
        discovery_ms = 0
        scrape_ms = 0
        persist_ms = 0
        hard_error: str | None = None
        per_marketplace_seed: dict[UUID, dict[str, Any]] = {}
        try:
            job_uuid = UUID(str(parent_job_id))
            async with session_factory() as db:
                parent = await db.get(ScrapeJob, job_uuid)
                if parent is None:
                    return {"status": "not_found", "job_id": str(job_uuid)}

                metadata = _extract_pipeline_metadata(parent.config)
                metadata["current_stage"] = "discovery"
                metadata["celery_task_id"] = self.request.id
                parent.config = {"metadata": metadata}
                await db.commit()

                discovery_started = time.perf_counter()
                _seen, per_marketplace_seed, discovery_errors = await _discover_for_full_pipeline(db)
                discovery_ms = int((time.perf_counter() - discovery_started) * 1000)

                metadata = _extract_pipeline_metadata(parent.config)
                metadata["current_stage"] = "scrape"
                metadata["discovery_errors"] = discovery_errors[:20]
                parent.config = {"metadata": metadata}
                await db.commit()

            scrape_started = time.perf_counter()
            scrape_result = _run_scrape_all_pool(scrape_job_id=job_uuid)
            scrape_ms = int((time.perf_counter() - scrape_started) * 1000)

            persist_started = time.perf_counter()
            async with session_factory() as db:
                parent = await db.get(ScrapeJob, job_uuid)
                if parent is None:
                    return {"status": "not_found", "job_id": str(job_uuid)}
                if scrape_result.get("error"):
                    hard_error = str(scrape_result["error"])
                persist_ms = int((time.perf_counter() - persist_started) * 1000)

                metadata = await _finalize_full_pipeline_job(
                    db,
                    parent,
                    discovery_ms=discovery_ms,
                    scrape_ms=scrape_ms,
                    persist_ms=persist_ms,
                    per_marketplace_seed=per_marketplace_seed,
                    hard_error=hard_error,
                )
                return {
                    "job_id": str(parent.id),
                    "status": parent.status,
                    "summary": metadata.get("summary", {}),
                }
        except Exception:
            tb = traceback.format_exc()
            hard_error = tb
            slog.exception("run_full_pipeline_test_failed", parent_job_id=parent_job_id)
            try:
                async with session_factory() as db:
                    job_uuid = UUID(str(parent_job_id))
                    parent = await db.get(ScrapeJob, job_uuid)
                    if parent is not None:
                        await _finalize_full_pipeline_job(
                            db,
                            parent,
                            discovery_ms=discovery_ms,
                            scrape_ms=scrape_ms,
                            persist_ms=persist_ms,
                            per_marketplace_seed=per_marketplace_seed,
                            hard_error=hard_error,
                        )
            except Exception:
                slog.exception("run_full_pipeline_test_mark_failed_error", parent_job_id=parent_job_id)
            return {
                "job_id": parent_job_id,
                "status": "failed",
                "error": "pipeline_execution_failed",
            }
        finally:
            await engine.dispose()

    return _run_async(_do())


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


