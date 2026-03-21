"""Admin API endpoints for scraper control (v2 migration stubs)."""

from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends

from app.common.deps import CurrentSuperuser, DbSession, get_current_superuser
from app.modules.scraper.tasks import (
    discover_all_marketplaces,
    discover_single_marketplace,
    scrape_all,
    scrape_all_pool_products,
)

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
    return {"message": "Scrape task queued", "task_id": str(task.id)}


@router.post("/discovery/trigger/{marketplace_id}")
async def trigger_discovery(
    marketplace_id: UUID,
    _current_user: CurrentSuperuser,
    _db: DbSession,
) -> dict:
    """Manually trigger discovery for one marketplace."""
    discover_single_marketplace.delay(str(marketplace_id))
    return {"status": "queued", "marketplace_id": str(marketplace_id)}


@router.post("/discovery/trigger-all")
async def trigger_discovery_all(_current_user: CurrentSuperuser, _db: DbSession) -> dict:
    """Manually trigger discovery for all active marketplaces."""
    discover_all_marketplaces.delay()
    return {"status": "queued"}


@router.post("/pool/trigger-scrape")
async def trigger_pool_scrape(_current_user: CurrentSuperuser, _db: DbSession) -> dict:
    """Manually trigger scraping of stale pool products."""
    scrape_all_pool_products.delay()
    return {"status": "queued"}


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
