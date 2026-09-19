"""Marketplace admin API (dim_marketplace CRUD)."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from app.common.deps import CurrentSuperuser, DbSession, get_current_superuser
from app.models.dimensions import DimCountry, DimMarketplace
from app.modules.marketplaces.schemas import (
    AdminMarketplaceListItem,
    CountryRef,
    MarketplaceCreateByUrl,
    MarketplaceUpdate,
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


def _to_admin_row(mp: DimMarketplace) -> AdminMarketplaceListItem:
    return AdminMarketplaceListItem(
        marketplace_id=str(mp.id),
        name=mp.name,
        domain=mp.domain,
        country_code=mp.country_code,
        country=mp.country_code,
        source="admin",
        is_active=mp.is_active,
        last_scrape_at=mp.last_scrape_at,
        last_scrape_status=_normalize_scrape_status(mp.last_scrape_status),
        products_count=mp.products_in_pool,
    )


@router.get("/countries", response_model=list[CountryRef])
async def list_marketplace_countries(
    db: DbSession,
    _current_user: CurrentSuperuser,
) -> list[CountryRef]:
    """Active dim_country rows for admin marketplace create/edit picker."""
    result = await db.execute(
        select(
            DimCountry.country_code,
            DimCountry.name,
            DimCountry.name_local,
            DimCountry.currency_code,
        )
        .where(DimCountry.is_active.is_(True))
        .order_by((DimCountry.country_code == "ZZ"), DimCountry.name),
    )
    return [
        CountryRef(
            code=row.country_code,
            name=row.name,
            name_local=row.name_local,
            currency_code=row.currency_code,
        )
        for row in result.all()
    ]


@router.get("", response_model=list[AdminMarketplaceListItem])
async def list_marketplaces(
    db: DbSession,
    _current_user: CurrentSuperuser,
) -> list[AdminMarketplaceListItem]:
    svc = MarketplaceService(db)
    items = await svc.list_marketplaces()
    return [_to_admin_row(m) for m in items]


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
        mp, _is_new = await svc.add_by_url(url, country_code=body.country_code)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return _to_admin_row(mp)


@router.patch("/{marketplace_id}", response_model=AdminMarketplaceListItem)
async def update_marketplace(
    marketplace_id: UUID,
    body: MarketplaceUpdate,
    db: DbSession,
    _current_user: CurrentSuperuser,
) -> AdminMarketplaceListItem:
    """Update marketplace name, URL, country, or active flag."""
    svc = MarketplaceService(db)
    payload = body.model_dump(exclude_unset=True)
    url = payload.pop("url", None)
    try:
        mp = await svc.update_marketplace(marketplace_id, payload, url=url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    if mp is None:
        raise HTTPException(status_code=404, detail="Marketplace not found")
    return _to_admin_row(mp)


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
