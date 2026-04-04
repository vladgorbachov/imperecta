"""Admin API endpoints for scraper control (v2 migration stubs)."""

import logging
import socket
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse
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


def _decodo_tcp_reachable(api_url: str) -> bool:
    """Return True if Decodo API host accepts TCP (no mock payload; infrastructure check)."""
    try:
        parsed = urlparse(api_url)
        host = parsed.hostname
        if not host:
            return False
        port = parsed.port or (443 if (parsed.scheme or "https") == "https" else 80)
        with socket.create_connection((host, int(port)), timeout=2.0):
            pass
        return True
    except OSError:
        return False


def _serialize_pool_result(r: PoolScrapeResult) -> dict:
    """Serialize PoolScrapeResult for JSON responses (Swagger-friendly dict)."""
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


async def _sample_result_from_db(db: DbSession) -> dict | None:
    """Last successful scrape log, serialized as PoolScrapeResult shape (real DB fields only)."""
    stmt = (
        select(ScrapeLog)
        .where(ScrapeLog.status == "success")
        .order_by(ScrapeLog.created_at.desc())
        .limit(1)
    )
    row = (await db.execute(stmt)).scalar_one_or_none()
    if row is None:
        return None
    data: ExtractedProduct | None = None
    if row.price_found is not None:
        data = ExtractedProduct(
            title=None,
            price=float(row.price_found),
            currency=None,
        )
    fields_extracted: list[str] = []
    fields_missing: list[str] = []
    if data is not None:
        fields_extracted = [k for k, v in asdict(data).items() if v is not None]
        fields_missing = [k for k, v in asdict(data).items() if v is None]
    pr = PoolScrapeResult(
        success=True,
        url=row.url,
        error=None,
        data=data,
        scraper_layer=row.scraper_type,
        duration_ms=row.duration_ms,
        is_partial=bool(data is not None and data.title is None),
        is_empty=data is None,
        fields_extracted=fields_extracted,
        fields_missing=fields_missing,
    )
    return _serialize_pool_result(pr)


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


@router.get("/scrape-diagnostics")
async def get_scrape_diagnostics(
    db: DbSession,
    _current_user: CurrentSuperuser,
) -> dict:
    """Pool metrics, recent logs, Decodo status, last successful scrape shape (DB-backed)."""
    settings = Settings()
    now = datetime.now(timezone.utc)
    since = now - timedelta(hours=24)

    total_stmt = (
        select(func.count()).select_from(FactListing).where(FactListing.is_active.is_(True))
    )
    total_listings = int((await db.execute(total_stmt)).scalar_one() or 0)

    priced_stmt = (
        select(func.count())
        .select_from(FactListing)
        .where(FactListing.is_active.is_(True))
        .where(FactListing.last_checked_at.is_not(None))
        .where(FactListing.last_checked_at >= since)
        .where(FactListing.last_price.is_not(None))
    )
    with_price_last_24h = int((await db.execute(priced_stmt)).scalar_one() or 0)

    log_stmt = select(ScrapeLog).order_by(ScrapeLog.created_at.desc()).limit(5)
    log_rows = (await db.execute(log_stmt)).scalars().all()
    last_5_logs = [
        {
            "status": row.status,
            "url": row.url,
            "price_found": float(row.price_found) if row.price_found is not None else None,
            "duration_ms": row.duration_ms,
        }
        for row in log_rows
    ]

    decodo_ready = bool(
        settings.decodo_enabled
        and settings.decodo_username
        and settings.decodo_password,
    )
    healthy = False
    if decodo_ready:
        healthy = bool(await run_in_threadpool(_decodo_tcp_reachable, settings.decodo_api_url))

    decodo_status = {
        "enabled": bool(settings.decodo_enabled),
        "healthy": healthy,
    }

    sample_result = await _sample_result_from_db(db)

    return {
        "total_listings": total_listings,
        "with_price_last_24h": with_price_last_24h,
        "last_5_logs": last_5_logs,
        "decodo_status": decodo_status,
        "sample_result": sample_result,
    }


@router.post("/scrape/test-single/{listing_id}")
async def test_single_scrape(
    listing_id: UUID,
    _current_user: CurrentSuperuser,
) -> dict:
    """Run one pool scrape synchronously; returns full PoolScrapeResult (GlobalScrapeService)."""

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
