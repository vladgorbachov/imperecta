"""Celery tasks for discovery and scraping (v2 dim/fact tables)."""

import asyncio
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import case, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import Settings
from app.database import sync_session_factory
from app.models.app_tables import ScrapeJob, ScrapeLog
from app.models.dimensions import DimMarketplace
from app.models.facts import FactListing
from app.modules.marketplaces.service import MarketplacePoolService
from app.modules.admin.parsing_admin import ParsingAdminService
from app.modules.scraper.discovery import DiscoveryCrawler
from app.modules.scraper.pipeline.job_completion import complete_pipeline_job as _finalize_full_pipeline_job
from app.modules.scraper.pipeline.activity_pulse import pulse_job_activity_sync
from app.modules.scraper.scraper_pool import ScraperPool
from app.modules.scraper.service import GlobalScrapeService
from app.workers.celery_app import celery_app

slog = structlog.get_logger(__name__)
_SCRAPE_LOG_STATUSES = (
    "success",
    "no_change",
    "error",
    "timeout",
    "blocked",
    "captcha",
    "not_found",
    "price_not_found",
    "parse_error",
    "missing_critical_data",
    "technical_error",
)


def _run_async(coro):
    """Run async coroutine from sync Celery task safely."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    with ThreadPoolExecutor(max_workers=1, thread_name_prefix="tasks-async-bridge") as executor:
        future = executor.submit(asyncio.run, coro)
        return future.result()


def _needs_scrape_logs_constraint_repair(exc: Exception) -> bool:
    """Detect old scrape_logs CHECK that rejects technical_error."""
    message = str(exc).lower()
    if "scrape_logs" not in message:
        return False
    if "technical_error" not in message:
        return False
    return (
        "scrape_logs_status_check" in message
        or "ck_scrape_logs_status" in message
        or "check constraint" in message
    )


def _repair_scrape_logs_status_constraint(db) -> bool:
    """Repair scrape_logs status CHECK to include technical_error."""
    allowed = ",".join(f"'{status}'" for status in _SCRAPE_LOG_STATUSES)
    try:
        db.execute(text("ALTER TABLE scrape_logs DROP CONSTRAINT IF EXISTS ck_scrape_logs_status"))
        db.execute(text("ALTER TABLE scrape_logs DROP CONSTRAINT IF EXISTS scrape_logs_status_check"))
        db.execute(
            text(
                "ALTER TABLE scrape_logs "
                "ADD CONSTRAINT ck_scrape_logs_status "
                f"CHECK (status IN ({allowed}))"
            )
        )
        db.commit()
        return True
    except Exception:
        db.rollback()
        return False


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
    entry: ScrapeLog | None = None
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
    except Exception as exc:
        needs_repair = entry is not None and _needs_scrape_logs_constraint_repair(exc)
        if needs_repair:
            db.rollback()
        if needs_repair and _repair_scrape_logs_status_constraint(db):
            try:
                db.add(entry)
                db.commit()
                slog.info("technical_error_logged", listing_id=str(listing_id))
                return
            except Exception:
                slog.exception("technical_error_persist_failed", listing_id=str(listing_id))
                try:
                    db.rollback()
                except Exception:
                    pass
        else:
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
    settings = Settings()
    threshold = datetime.now(timezone.utc) - timedelta(hours=6)
    batch_size = max(int(settings.scrape_pool_batch_size or 1000), 1)
    max_listings_per_run = max(int(settings.scrape_pool_max_listings_per_run or 200000), 1)
    queued_total = 0
    processed_ids: set[UUID] = set()
    ok = 0
    failed = 0
    db = sync_session_factory()
    try:
        svc = GlobalScrapeService(db, scraper_pool, scrape_job_id=scrape_job_id)
        while queued_total < max_listings_per_run:
            result = db.execute(
                select(FactListing.id)
                .where(FactListing.is_active.is_(True))
                .where(
                    or_(
                        FactListing.last_checked_at.is_(None),
                        FactListing.last_checked_at < threshold,
                    ),
                )
                .limit(batch_size),
            )
            batch_ids = [r[0] for r in result.all()]
            if not batch_ids:
                break

            stale_ids = [listing_id for listing_id in batch_ids if listing_id not in processed_ids]
            if not stale_ids:
                # Safety guard for mocked/inconsistent sessions returning the same rows repeatedly.
                break

            remaining = max_listings_per_run - queued_total
            stale_ids = stale_ids[:remaining]
            if not stale_ids:
                break

            queued_total += len(stale_ids)
            processed_ids.update(stale_ids)
            slog.info(
                "scrape_all_pool_batch",
                batch_size=len(stale_ids),
                queued_total=queued_total,
                max_listings_per_run=max_listings_per_run,
            )
            if scrape_job_id is not None:
                pulse_job_activity_sync(
                    scrape_job_id,
                    f"scrape batch {len(stale_ids)} listings (queued {queued_total})",
                    stage="scrape",
                    force_db=True,
                )

            for index, lid in enumerate(stale_ids):
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
                    if scrape_job_id is not None:
                        status_label = "ok" if r.success else "fail"
                        pulse_job_activity_sync(
                            scrape_job_id,
                            f"scrape {status_label} {url_hint}",
                            stage="scrape",
                            force_db=index % 10 == 0,
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
                    if scrape_job_id is not None:
                        pulse_job_activity_sync(
                            scrape_job_id,
                            f"scrape error {str(lid)[:8]}",
                            stage="scrape",
                            force_db=True,
                        )
                    failed += 1
    finally:
        db.close()

    slog.info(
        "scrape_all_pool_products_finished",
        eligible=queued_total,
        ok=ok,
        failed=failed,
    )
    return {
        "queued": queued_total,
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


def _touch_pipeline_metadata(
    metadata: dict[str, Any],
    *,
    stage: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Update pipeline heartbeat metadata in-place and return it."""
    touched_at = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat()
    metadata["last_activity_at"] = touched_at
    if stage is not None:
        metadata["current_stage"] = stage
    return metadata


async def _discover_for_full_pipeline(
    db: AsyncSession,
    on_progress: Any | None = None,
) -> tuple[int, dict[UUID, dict[str, Any]], list[str]]:
    result = await db.execute(
        select(DimMarketplace)
        .where(DimMarketplace.is_active.is_(True))
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
            if on_progress is not None:
                await on_progress()
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
            if on_progress is not None:
                await on_progress()
    return len(marketplaces), per_marketplace, errors


@celery_app.task(
    bind=True,
    name="run_full_pipeline_test",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 1},
)
def run_full_pipeline_test(self, parent_job_id: str) -> dict:
    """Run discovery + scrape pipeline for admin parsing jobs."""

    async def _do() -> dict:
        from app.modules.scraper.pipeline.orchestrator import FullPipelineOrchestrator

        engine, session_factory = _make_session_factory()
        try:
            runner = FullPipelineOrchestrator(
                session_factory,
                celery_task_id=str(self.request.id),
            )
            return await runner.run(UUID(str(parent_job_id)))
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


