"""Marketplace pool admin API endpoints."""

from typing import Any

from fastapi import APIRouter, Body, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, HttpUrl
from sqlalchemy import and_, delete, func, select, update
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
    """Get scrape stats for a marketplace from scrape_logs. Used by logs endpoint."""
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


@router.post("/recalculate-quotas")
async def recalculate_quotas(db: DbSession, _current_user: CurrentSuperuser) -> dict:
    """
    Recalculate product_quota for all active marketplaces.
    Formula: 50000 / active_marketplace_count (equal quota each).
    Must be called after adding/removing marketplaces.
    """
    service = MarketplacePoolService(db)
    await service.recalculate_all_quotas()
    marketplaces = await service.list_all(is_active=True)
    quota = marketplaces[0].product_quota if marketplaces else 0
    return {
        "status": "recalculated",
        "active_marketplaces": len(marketplaces),
        "quota_per_marketplace": quota,
        "total_pool_capacity": 50_000,
    }


@router.post("/set-requires-js")
async def set_requires_js(
    _current_user: CurrentSuperuser,
    db: DbSession,
    domains: list[str] = Body(..., embed=True),
) -> dict:
    """
    Mark specific marketplaces as requiring JS rendering (Playwright).
    Use for SPA sites like ozon.ru, rozetka.com.ua, wildberries.ru.

    Body: {"domains": ["ozon.ru", "rozetka.com.ua", "wildberries.ru"]}
    """
    result = await db.execute(
        update(AdminMarketplace)
        .where(AdminMarketplace.domain.in_(domains))
        .values(requires_js=True)
    )
    await db.commit()
    return {"updated": result.rowcount, "domains": domains}


@router.get("")
async def admin_marketplaces(db: DbSession, _current_user: CurrentSuperuser) -> list[dict]:
    """Return all marketplaces (registry + admin) with stats. Batched queries to avoid N+1."""
    admin_result = await db.execute(select(AdminMarketplace))
    admin_list = admin_result.scalars().all()

    all_ids = [r["marketplace_id"] for r in MARKETPLACE_REGISTRY]
    all_ids.extend(am.marketplace_id for am in admin_list)
    all_ids = list(dict.fromkeys(all_ids))

    if not all_ids:
        return []

    # Batch 1: scrape stats (total, successful, last_scrape_at) per marketplace
    stats_stmt = (
        select(
            ScrapeLog.marketplace_id,
            func.count().label("total"),
            func.count().filter(ScrapeLog.status == "success").label("successful"),
            func.max(ScrapeLog.created_at).label("last_scrape_at"),
        )
        .where(ScrapeLog.marketplace_id.in_(all_ids))
        .group_by(ScrapeLog.marketplace_id)
    )
    stats_rows = (await db.execute(stats_stmt)).all()
    stats_map = {r.marketplace_id: r for r in stats_rows}

    # Batch 2: last status per marketplace (most recent row, PostgreSQL DISTINCT ON)
    last_status_stmt = (
        select(ScrapeLog.marketplace_id, ScrapeLog.status)
        .where(ScrapeLog.marketplace_id.in_(all_ids))
        .distinct(ScrapeLog.marketplace_id)
        .order_by(ScrapeLog.marketplace_id, ScrapeLog.created_at.desc())
    )
    last_status_rows = (await db.execute(last_status_stmt)).all()
    last_status_map = {r.marketplace_id: r.status for r in last_status_rows}

    # Batch 3: last error per marketplace (most recent failed row)
    last_error_stmt = (
        select(ScrapeLog.marketplace_id, ScrapeLog.error_message)
        .where(
            ScrapeLog.marketplace_id.in_(all_ids),
            ScrapeLog.status != "success",
        )
        .distinct(ScrapeLog.marketplace_id)
        .order_by(ScrapeLog.marketplace_id, ScrapeLog.created_at.desc())
    )
    try:
        last_error_rows = (await db.execute(last_error_stmt)).all()
    except Exception:
        last_error_rows = []
    last_error_map = {r.marketplace_id: r.error_message for r in last_error_rows}

    # Batch 4: products_count per marketplace
    cp_count_stmt = (
        select(Competitor.marketplace, func.count(CompetitorProduct.id).label("cnt"))
        .select_from(CompetitorProduct)
        .join(Competitor, CompetitorProduct.competitor_id == Competitor.id)
        .where(Competitor.marketplace.in_(all_ids))
        .group_by(Competitor.marketplace)
    )
    cp_count_rows = (await db.execute(cp_count_stmt)).all()
    products_count_map = {r.marketplace: r.cnt for r in cp_count_rows}

    result_list: list[dict] = []

    for reg in MARKETPLACE_REGISTRY:
        mid = reg["marketplace_id"]
        row = stats_map.get(mid)
        total = row.total or 0 if row else 0
        successful = row.successful or 0 if row else 0
        failed = total - successful
        success_rate = round((successful / total * 100) if total else 0, 1)
        last_scrape_at = row.last_scrape_at if row else None
        products_count = products_count_map.get(mid, 0)

        result_list.append({
            "marketplace_id": mid,
            "name": reg["name"],
            "domain": reg["domain"],
            "country": reg["country"],
            "region": reg["region"],
            "source": "registry",
            "is_active": True,
            "last_scrape_at": last_scrape_at.isoformat() if last_scrape_at else None,
            "last_scrape_status": last_status_map.get(mid),
            "last_error": last_error_map.get(mid),
            "total_scrapes": total,
            "successful_scrapes": successful,
            "failed_scrapes": failed,
            "success_rate": success_rate,
            "products_count": products_count,
        })

    for am in admin_list:
        mid = am.marketplace_id
        row = stats_map.get(mid)
        total = am.total_scrapes or (row.total or 0 if row else 0)
        successful = am.successful_scrapes or (row.successful or 0 if row else 0)
        failed = am.failed_scrapes or (total - successful)
        success_rate = round((successful / total * 100) if total else 0, 1)
        products_count = products_count_map.get(mid, 0)

        last_at = am.last_scrape_at or (row.last_scrape_at if row else None)
        result_list.append({
            "marketplace_id": mid,
            "name": am.name,
            "domain": am.domain,
            "country": am.country,
            "region": am.region,
            "source": "admin",
            "is_active": am.is_active,
            "last_scrape_at": last_at.isoformat() if last_at else None,
            "last_scrape_status": am.last_scrape_status or last_status_map.get(mid),
            "last_error": am.last_error or last_error_map.get(mid),
            "total_scrapes": total,
            "successful_scrapes": successful,
            "failed_scrapes": failed,
            "success_rate": success_rate,
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
