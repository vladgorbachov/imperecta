"""Admin API endpoints for scraper control (v2 migration stubs)."""

import logging
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import func, select

from app.common.deps import CurrentSuperuser, DbSession, get_current_superuser
from app.config import Settings
from app.database import sync_session_factory
from app.models.app_tables import ScrapeLog
from app.models.facts import FactListing
from app.modules.scraper.extractors import ExtractedProduct
from app.modules.scraper.scraper_pool import PoolScrapeResult, ScraperPool
from app.modules.scraper.service import GlobalScrapeService
from app.modules.scraper.tasks import (
    discover_all_marketplaces,
    discover_single_marketplace,
    scrape_all,
    scrape_all_pool_products,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/admin",
    tags=["scraper"],
    dependencies=[Depends(get_current_superuser)],
)

_MIGRATION_MSG = "Pending migration to v2 schema"


@router.post("/trigger-scrape")
async def admin_trigger_scrape(_current_user: CurrentSuperuser, _db: DbSession) -> dict:
    """Manually trigger scraping for stale pool listings."""
    task = scrape_all.delay()
    logger.info("admin POST trigger-scrape task_id=%s", task.id)
    return {"message": "Scrape task queued", "task_id": str(task.id)}


@router.post("/discovery/trigger/{marketplace_id}")
async def trigger_discovery(
    marketplace_id: UUID,
    _current_user: CurrentSuperuser,
    _db: DbSession,
) -> dict:
    """Manually trigger discovery for one marketplace."""
    async_result = discover_single_marketplace.delay(str(marketplace_id))
    logger.info(
        "admin POST discovery/trigger marketplace_id=%s task_id=%s",
        marketplace_id,
        async_result.id,
    )
    return {
        "status": "queued",
        "marketplace_id": str(marketplace_id),
        "task_id": str(async_result.id),
    }


@router.post("/discovery/trigger-all")
async def trigger_discovery_all(_current_user: CurrentSuperuser, _db: DbSession) -> dict:
    """Manually trigger discovery for all active marketplaces."""
    async_result = discover_all_marketplaces.delay()
    logger.info("admin POST discovery/trigger-all task_id=%s", async_result.id)
    return {"status": "queued", "task_id": str(async_result.id)}


@router.post("/pool/trigger-scrape")
async def trigger_pool_scrape(_current_user: CurrentSuperuser, _db: DbSession) -> dict:
    """Manually trigger scraping of stale pool products."""
    async_result = scrape_all_pool_products.delay()
    logger.info("admin POST pool/trigger-scrape task_id=%s", async_result.id)
    return {"status": "queued", "task_id": str(async_result.id)}


@router.get("/scrape-activity")
async def admin_scrape_activity(_db: DbSession, _current_user: CurrentSuperuser) -> dict:
    """Return scrape activity data for chart (placeholder)."""
    now = datetime.now(timezone.utc)
    labels = []
    for i in range(6, -1, -1):
        day_start = (now - timedelta(days=i)).replace(hour=0, minute=0, second=0, microsecond=0)
        labels.append(day_start.strftime("%Y-%m-%d"))
    return {
        "labels": labels,
        "datasets": [
            {"label": "Успешно", "data": [0] * 7},
            {"label": "Ошибки", "data": [0] * 7},
        ],
        "message": _MIGRATION_MSG,
    }


@router.get("/error-distribution")
async def admin_error_distribution(_db: DbSession, _current_user: CurrentSuperuser) -> dict:
    """Return error distribution for pie chart (placeholder)."""
    categories = ["timeout", "blocked", "selector_not_found", "connection_error", "other"]
    return {
        "labels": categories,
        "data": [0] * len(categories),
        "message": _MIGRATION_MSG,
    }


def _pool_scrape_result_example() -> dict:
    """JSON-serializable example for diagnostics (no outbound HTTP)."""
    sample = PoolScrapeResult(
        success=True,
        url="https://example.com/product/sample",
        error=None,
        data=ExtractedProduct(
            title="Sample product",
            price=19.99,
            currency="USD",
            image_url="https://example.com/img.jpg",
        ),
        scraper_layer="httpx",
        duration_ms=850,
        is_partial=False,
        is_empty=False,
        fields_extracted=["title", "price", "currency", "image_url"],
        fields_missing=["description"],
    )
    d = asdict(sample)
    if sample.data:
        d["data"] = asdict(sample.data)
    return d


def _serialize_pool_result(r: PoolScrapeResult) -> dict:
    """Serialize scrape result for admin test-single response."""
    out: dict = {
        "success": r.success,
        "url": r.url,
        "error": r.error,
        "scraper_layer": r.scraper_layer,
        "duration_ms": r.duration_ms,
        "is_partial": r.is_partial,
        "is_empty": r.is_empty,
        "fields_extracted": list(r.fields_extracted),
        "fields_missing": list(r.fields_missing),
    }
    if r.data:
        out["data"] = asdict(r.data)
    else:
        out["data"] = None
    return out


@router.get("/scrape-diagnostics")
async def scrape_diagnostics(
    db: DbSession,
    _current_user: CurrentSuperuser,
) -> dict:
    """Listings without price after recent checks, latest logs, Decodo, sample result shape."""
    settings = Settings()
    now = datetime.now(timezone.utc)
    since = now - timedelta(hours=24)

    cnt_stmt = (
        select(func.count())
        .select_from(FactListing)
        .where(FactListing.is_active.is_(True))
        .where(FactListing.last_checked_at.is_not(None))
        .where(FactListing.last_checked_at >= since)
        .where(FactListing.last_price.is_(None))
    )
    res_count = await db.execute(cnt_stmt)
    no_price_24h = int(res_count.scalar_one() or 0)

    log_stmt = select(ScrapeLog).order_by(ScrapeLog.created_at.desc()).limit(5)
    log_rows = (await db.execute(log_stmt)).scalars().all()
    top_logs = [
        {
            "id": row.id,
            "listing_id": str(row.listing_id),
            "status": row.status,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "error_message": (row.error_message or "")[:500],
            "scraper_type": row.scraper_type,
        }
        for row in log_rows
    ]

    decodo = {
        "enabled": bool(settings.decodo_enabled),
        "configured": bool(
            settings.decodo_enabled
            and settings.decodo_username
            and settings.decodo_password,
        ),
        "api_url": settings.decodo_api_url,
    }

    return {
        "listings_no_price_checked_24h": no_price_24h,
        "latest_scrape_logs_top5": top_logs,
        "decodo": decodo,
        "pool_scrape_result_example": _pool_scrape_result_example(),
    }


@router.post("/scrape/test-single/{listing_id}")
async def admin_scrape_test_single(
    listing_id: UUID,
    _current_user: CurrentSuperuser,
) -> dict:
    """Run GlobalScrapeService.scrape_product synchronously; return full structured result."""

    def _run() -> dict:
        session = sync_session_factory()
        try:
            pool = ScraperPool()
            svc = GlobalScrapeService(session, pool)
            result = svc.scrape_product(listing_id)
            return {
                "listing_id": str(listing_id),
                "result": _serialize_pool_result(result),
            }
        finally:
            session.close()

    return await run_in_threadpool(_run)
