"""Marketplace pool admin API endpoints."""

from typing import Any

from fastapi import APIRouter, Body, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, HttpUrl
from sqlalchemy import and_, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.deps import CurrentSuperuser, DbSession, get_current_superuser
from app.models import Competitor, CompetitorProduct, ScrapeLog
from app.modules.marketplaces.models import AdminMarketplace
from app.modules.marketplaces.service import MarketplacePoolService

router = APIRouter(
    prefix="/admin/marketplaces",
    tags=["marketplaces"],
    dependencies=[Depends(get_current_superuser)],
)

# Built-in marketplace registry for admin stats. All marketplaces treated equally.
MARKETPLACE_REGISTRY: list[dict[str, Any]] = [
    {"marketplace_id": "ozon", "name": "Ozon", "domain": "ozon.ru", "country": "RU", "region": "cis"},
    {"marketplace_id": "wildberries", "name": "Wildberries", "domain": "wildberries.ru", "country": "RU", "region": "cis"},
    {"marketplace_id": "kaspi", "name": "Kaspi", "domain": "kaspi.kz", "country": "KZ", "region": "cis"},
]


async def _get_marketplace_scrape_stats(db: AsyncSession, marketplace_id: str) -> dict:
    """Get scrape stats for a marketplace from scrape_logs."""
    result = await db.execute(
        select(
            func.count().label("total"),
            func.count().filter(ScrapeLog.status == "success").label("successful"),
            func.max(ScrapeLog.created_at).label("last_scrape_at"),
        ).where(ScrapeLog.marketplace_id == marketplace_id)
    )
    row = result.one()
    total = row.total or 0
    successful = row.successful or 0
    failed = total - successful
    success_rate = (successful / total * 100) if total else 0

    last_error_result = await db.execute(
        select(ScrapeLog.error_message, ScrapeLog.created_at)
        .where(and_(ScrapeLog.marketplace_id == marketplace_id, ScrapeLog.status != "success"))
        .order_by(ScrapeLog.created_at.desc())
        .limit(1)
    )
    last_err = last_error_result.one_or_none()
    last_status_result = await db.execute(
        select(ScrapeLog.status)
        .where(ScrapeLog.marketplace_id == marketplace_id)
        .order_by(ScrapeLog.created_at.desc())
        .limit(1)
    )
    last_status = last_status_result.scalar_one_or_none()

    return {
        "total_scrapes": total,
        "successful_scrapes": successful,
        "failed_scrapes": failed,
        "success_rate": round(success_rate, 1),
        "last_scrape_at": row.last_scrape_at,
        "last_scrape_status": last_status,
        "last_error": last_err.error_message if last_err else None,
    }


@router.get("")
async def admin_marketplaces(db: DbSession, _current_user: CurrentSuperuser) -> list[dict]:
    """Return all marketplaces (registry + admin) with stats."""
    result_list: list[dict] = []

    for reg in MARKETPLACE_REGISTRY:
        mid = reg["marketplace_id"]
        stats = await _get_marketplace_scrape_stats(db, mid)

        cp_count_result = await db.execute(
            select(func.count())
            .select_from(CompetitorProduct)
            .join(Competitor, CompetitorProduct.competitor_id == Competitor.id)
            .where(Competitor.marketplace == mid)
        )
        products_count = cp_count_result.scalar() or 0

        result_list.append({
            "marketplace_id": mid,
            "name": reg["name"],
            "domain": reg["domain"],
            "country": reg["country"],
            "region": reg["region"],
            "source": "registry",
            "is_active": True,
            "last_scrape_at": stats["last_scrape_at"].isoformat() if stats["last_scrape_at"] else None,
            "last_scrape_status": stats["last_scrape_status"],
            "last_error": stats["last_error"],
            "total_scrapes": stats["total_scrapes"],
            "successful_scrapes": stats["successful_scrapes"],
            "failed_scrapes": stats["failed_scrapes"],
            "success_rate": stats["success_rate"],
            "products_count": products_count,
        })

    admin_result = await db.execute(select(AdminMarketplace))
    for am in admin_result.scalars().all():
        stats = await _get_marketplace_scrape_stats(db, am.marketplace_id)

        cp_count_result = await db.execute(
            select(func.count())
            .select_from(CompetitorProduct)
            .join(Competitor, CompetitorProduct.competitor_id == Competitor.id)
            .where(Competitor.marketplace == am.marketplace_id)
        )
        products_count = cp_count_result.scalar() or 0

        result_list.append({
            "marketplace_id": am.marketplace_id,
            "name": am.name,
            "domain": am.domain,
            "country": am.country,
            "region": am.region,
            "source": "admin",
            "is_active": am.is_active,
            "last_scrape_at": am.last_scrape_at.isoformat() if am.last_scrape_at else None,
            "last_scrape_status": am.last_scrape_status or stats["last_scrape_status"],
            "last_error": am.last_error or stats["last_error"],
            "total_scrapes": am.total_scrapes,
            "successful_scrapes": am.successful_scrapes,
            "failed_scrapes": am.failed_scrapes,
            "success_rate": round((am.successful_scrapes / am.total_scrapes * 100) if am.total_scrapes else 0, 1),
            "products_count": products_count,
        })

    result_list.sort(key=lambda x: (x["name"].lower(),))
    return result_list


@router.get("/{marketplace_id}/logs")
async def admin_marketplace_logs(
    marketplace_id: str,
    db: DbSession,
    _current_user: CurrentSuperuser,
) -> list[dict]:
    """Return last 50 scrape logs for a marketplace."""
    result = await db.execute(
        select(ScrapeLog)
        .where(ScrapeLog.marketplace_id == marketplace_id)
        .order_by(ScrapeLog.created_at.desc())
        .limit(50)
    )
    logs = result.scalars().all()
    return [
        {
            "id": log.id,
            "url": log.url,
            "status": log.status,
            "error_message": log.error_message,
            "price_found": float(log.price_found) if log.price_found is not None else None,
            "duration_ms": log.duration_ms,
            "proxy_used": log.proxy_used,
            "created_at": log.created_at.isoformat(),
        }
        for log in logs
    ]


class AddMarketplaceRequest(BaseModel):
    """Request body for adding marketplace by URL."""

    url: HttpUrl


@router.post("")
async def admin_add_marketplace(
    data: AddMarketplaceRequest,
    db: DbSession,
    _current_user: CurrentSuperuser,
) -> dict:
    """Add new marketplace by URL."""
    service = MarketplacePoolService(db)
    try:
        am = await service.add_by_url(str(data.url))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return {
        "marketplace_id": am.marketplace_id,
        "name": am.name,
        "domain": am.domain,
        "base_url": am.base_url,
        "country": am.country,
        "region": am.region,
        "currency": am.currency,
        "scraper_type": am.scraper_type,
    }


@router.post("/add-by-url")
async def add_marketplace_by_url(
    _current_user: CurrentSuperuser,
    db: DbSession,
    url: str = Body(..., embed=True),
):
    """Add marketplace by URL. Auto-extracts domain, name, country."""
    service = MarketplacePoolService(db)
    try:
        mp = await service.add_by_url(url)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"id": mp.id, "domain": mp.domain, "name": mp.name}


@router.post("/import-file")
async def import_marketplaces_from_file(
    _current_user: CurrentSuperuser,
    db: DbSession,
    file: UploadFile = File(...),
):
    """
    Import marketplaces from .txt or .csv file.
    .txt: one URL per line
    .csv: column 'url' or first column
    """
    content = (await file.read()).decode("utf-8")
    service = MarketplacePoolService(db)

    if file.filename and file.filename.endswith(".csv"):
        result = await service.import_from_csv(content)
    else:
        result = await service.import_from_txt(content)

    return result


@router.delete("/{marketplace_id}")
async def admin_delete_marketplace(
    marketplace_id: str,
    db: DbSession,
    _current_user: CurrentSuperuser,
) -> dict:
    """Delete marketplace (only from admin_marketplaces, not registry)."""
    for reg in MARKETPLACE_REGISTRY:
        if reg["marketplace_id"] == marketplace_id:
            raise HTTPException(status_code=403, detail="Cannot delete built-in marketplace")

    result = await db.execute(
        delete(AdminMarketplace).where(AdminMarketplace.marketplace_id == marketplace_id)
    )
    await db.flush()
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Marketplace not found")
    service = MarketplacePoolService(db)
    await service.recalculate_all_quotas()
    return {"ok": True}
