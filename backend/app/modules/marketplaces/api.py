"""Marketplace admin API (dim_marketplace CRUD)."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select

from app.common.deps import CurrentSuperuser, DbSession, get_current_superuser
from app.models.app_tables import ScrapeLog
from app.models.dimensions import DimCountry, DimMarketplace
from app.modules.marketplaces.schemas import (
    AdminMarketplaceListItem,
    ImportTextBody,
    MarketplaceCreateByUrl,
    MarketplaceResponse,
    SetRequiresJsBody,
)
from app.modules.marketplaces.service import MarketplaceService

router = APIRouter(
    prefix="/admin/marketplaces",
    tags=["marketplaces"],
    dependencies=[Depends(get_current_superuser)],
)


def _normalize_scrape_status(
    raw: str | None,
) -> Literal["success", "error", "timeout", "blocked"] | None:
    if not raw:
        return None
    s = raw.strip().lower()
    if s in ("success", "ok", "completed", "done"):
        return "success"
    if s in ("error", "failed", "fail"):
        return "error"
    if s in ("timeout", "timed_out"):
        return "timeout"
    if s in ("blocked", "forbidden", "403", "429"):
        return "blocked"
    return "error"


def _to_admin_row(mp: DimMarketplace, region: str) -> AdminMarketplaceListItem:
    st = _normalize_scrape_status(mp.last_scrape_status)
    return AdminMarketplaceListItem(
        marketplace_id=str(mp.id),
        name=mp.name,
        domain=mp.domain,
        country=mp.country_code,
        region=region,
        source="admin",
        is_active=mp.is_active,
        last_scrape_at=mp.last_scrape_at,
        last_scrape_status=st,
        last_error=None,
        total_scrapes=0,
        successful_scrapes=0,
        failed_scrapes=0,
        success_rate=0.0,
        products_count=mp.products_in_pool,
    )


async def _regions_for_marketplaces(db, rows: list[DimMarketplace]) -> dict[str, str]:
    codes = {r.country_code for r in rows}
    if not codes:
        return {}
    result = await db.execute(
        select(DimCountry.country_code, DimCountry.region).where(
            DimCountry.country_code.in_(codes),
        ),
    )
    return {c: r for c, r in result.all()}


@router.get("", response_model=list[AdminMarketplaceListItem])
async def list_marketplaces(
    db: DbSession,
    _current_user: CurrentSuperuser,
) -> list[AdminMarketplaceListItem]:
    svc = MarketplaceService(db)
    items = await svc.list_marketplaces()
    regions = await _regions_for_marketplaces(db, items)
    return [_to_admin_row(m, regions.get(m.country_code, "")) for m in items]


@router.post("", response_model=AdminMarketplaceListItem)
async def add_marketplace_root(
    body: MarketplaceCreateByUrl,
    db: DbSession,
    _current_user: CurrentSuperuser,
) -> AdminMarketplaceListItem:
    url = (body.url or "").strip()
    if not url:
        raise HTTPException(status_code=400, detail="URL is required")
    svc = MarketplaceService(db)
    try:
        mp, _is_new = await svc.add_by_url(url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    regions = await _regions_for_marketplaces(db, [mp])
    return _to_admin_row(mp, regions.get(mp.country_code, ""))


@router.post("/add-by-url", response_model=MarketplaceResponse)
async def add_marketplace_by_url(
    body: MarketplaceCreateByUrl,
    db: DbSession,
    _current_user: CurrentSuperuser,
) -> MarketplaceResponse:
    url = (body.url or "").strip()
    if not url:
        raise HTTPException(status_code=400, detail="URL is required")
    svc = MarketplaceService(db)
    try:
        mp, _is_new = await svc.add_by_url(url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return MarketplaceResponse.model_validate(mp)


@router.post("/import-file")
async def import_marketplaces_file(
    db: DbSession,
    _current_user: CurrentSuperuser,
    file: UploadFile = File(...),
) -> dict:
    raw = await file.read()
    content = raw.decode("utf-8", errors="ignore")
    svc = MarketplaceService(db)
    return await svc.import_from_text(content)


@router.post("/import-text")
async def import_marketplaces_text(
    body: ImportTextBody,
    db: DbSession,
    _current_user: CurrentSuperuser,
) -> dict:
    svc = MarketplaceService(db)
    return await svc.import_from_text(body.content)


@router.delete("/{marketplace_id}")
async def delete_marketplace(
    marketplace_id: UUID,
    db: DbSession,
    _current_user: CurrentSuperuser,
) -> dict:
    svc = MarketplaceService(db)
    deleted = await svc.delete_marketplace(marketplace_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Marketplace not found")
    return {"deleted": True}


@router.post("/recalculate-quotas")
async def recalculate_quotas(
    db: DbSession,
    _current_user: CurrentSuperuser,
) -> dict:
    svc = MarketplaceService(db)
    return await svc.recalculate_quotas()


@router.post("/set-requires-js", response_model=MarketplaceResponse)
async def set_requires_js(
    body: SetRequiresJsBody,
    db: DbSession,
    _current_user: CurrentSuperuser,
) -> MarketplaceResponse:
    svc = MarketplaceService(db)
    mp = await svc.update_marketplace(body.marketplace_id, {"requires_js": body.requires_js})
    if not mp:
        raise HTTPException(status_code=404, detail="Marketplace not found")
    return MarketplaceResponse.model_validate(mp)


@router.get("/{marketplace_id}/logs")
async def marketplace_logs(
    marketplace_id: UUID,
    db: DbSession,
    _current_user: CurrentSuperuser,
) -> list[dict]:
    result = await db.execute(
        select(ScrapeLog)
        .where(ScrapeLog.marketplace_id == marketplace_id)
        .order_by(ScrapeLog.created_at.desc())
        .limit(100)
    )
    rows = list(result.scalars().all())
    out: list[dict] = []
    for log in rows:
        proxy = log.proxy_used
        proxy_used = bool(proxy) if proxy not in (None, "", "false") else False
        out.append(
            {
                "id": int(log.id),
                "url": log.url,
                "status": log.status,
                "error_message": log.error_message,
                "price_found": float(log.price_found) if log.price_found is not None else None,
                "duration_ms": log.duration_ms,
                "proxy_used": proxy_used,
                "created_at": log.created_at.isoformat() if log.created_at else "",
            }
        )
    return out
