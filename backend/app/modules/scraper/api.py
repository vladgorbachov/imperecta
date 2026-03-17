"""Admin API endpoints for scraper control."""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import and_, func, select

from app.common.deps import CurrentSuperuser, DbSession, get_current_superuser
from app.modules.scraper.models import ScrapeLog
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


@router.post("/trigger-scrape")
async def admin_trigger_scrape(_current_user: CurrentSuperuser, _db: DbSession) -> dict:
    """Manually trigger scraping for all active competitor_products."""
    task = scrape_all.delay()
    return {"message": "Scrape task queued", "task_id": str(task.id)}


@router.post("/discovery/trigger/{marketplace_id}")
async def trigger_discovery(
    marketplace_id: int,
    _current_user: CurrentSuperuser,
    _db: DbSession,
) -> dict:
    """Manually trigger discovery for one marketplace."""
    discover_single_marketplace.delay(marketplace_id)
    return {"status": "queued", "marketplace_id": marketplace_id}


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
async def admin_scrape_activity(db: DbSession, _current_user: CurrentSuperuser) -> dict:
    """Return scrape activity data for chart (last 7 days)."""
    now = datetime.now(timezone.utc)
    labels = []
    success_data = []
    error_data = []

    for i in range(6, -1, -1):
        day_start = (now - timedelta(days=i)).replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        labels.append(day_start.strftime("%Y-%m-%d"))

        result = await db.execute(
            select(
                func.count().filter(ScrapeLog.status == "success").label("ok"),
                func.count().filter(ScrapeLog.status != "success").label("err"),
            ).where(and_(ScrapeLog.created_at >= day_start, ScrapeLog.created_at < day_end))
        )
        row = result.one()
        success_data.append(row.ok or 0)
        error_data.append(row.err or 0)

    return {
        "labels": labels,
        "datasets": [
            {"label": "Успешно", "data": success_data},
            {"label": "Ошибки", "data": error_data},
        ],
    }


def _categorize_error(message: str | None) -> str:
    """Map error message to category for distribution chart."""
    if not message:
        return "other"
    lowered = message.lower()
    if "timeout" in lowered:
        return "timeout"
    if "blocked" in lowered or "captcha" in lowered:
        return "blocked"
    if "selector" in lowered or "not found" in lowered or "extract" in lowered:
        return "selector_not_found"
    if "connection" in lowered or "connect" in lowered or "refused" in lowered:
        return "connection_error"
    return "other"


@router.get("/error-distribution")
async def admin_error_distribution(db: DbSession, _current_user: CurrentSuperuser) -> dict:
    """Return error distribution for pie chart (last 24h)."""
    day_ago = datetime.now(timezone.utc) - timedelta(hours=24)
    result = await db.execute(
        select(ScrapeLog.error_message).where(
            and_(ScrapeLog.created_at >= day_ago, ScrapeLog.status != "success")
        )
    )
    errors = [row[0] for row in result.all()]

    categories = ["timeout", "blocked", "selector_not_found", "connection_error", "other"]
    counts = {category: 0 for category in categories}
    for message in errors:
        category = _categorize_error(message)
        counts[category] = counts.get(category, 0) + 1

    return {
        "labels": categories,
        "data": [counts[category] for category in categories],
    }
