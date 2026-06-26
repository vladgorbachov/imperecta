"""Async operational reads for dashboard KPI aggregates (service-data, no access-log)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

from app.models.dimensions import DimMarketplace
from app.models.facts import FactListing

_INTERVAL_24H = text("INTERVAL '24 hours'")


def _apply_dashboard_kpi_filters(
    stmt: Select,
    *,
    country_code: str | None,
    marketplace_id: UUID | None,
) -> Select:
    """Mirror movements/read._apply_entity_filters for country and marketplace scope."""
    stmt = stmt.where(
        FactListing.is_active.is_(True),
        FactListing.page_role == "product",
    )
    if marketplace_id is not None:
        stmt = stmt.where(FactListing.marketplace_id == marketplace_id)
    if country_code:
        stmt = stmt.join(
            DimMarketplace,
            FactListing.marketplace_id == DimMarketplace.id,
        ).where(DimMarketplace.country_code == country_code.strip().upper())
    return stmt


async def read_dashboard_kpi(
    db: AsyncSession,
    *,
    country_code: str | None,
    marketplace_id: UUID | None,
) -> tuple[int, datetime | None]:
    """Return (updated_24h count, all-time max last_checked_at) for the visible pool."""
    updated_stmt = _apply_dashboard_kpi_filters(
        select(func.count()).select_from(FactListing),
        country_code=country_code,
        marketplace_id=marketplace_id,
    ).where(
        FactListing.last_checked_at.is_not(None),
        FactListing.last_checked_at >= func.now() - _INTERVAL_24H,
    )
    last_update_stmt = _apply_dashboard_kpi_filters(
        select(func.max(FactListing.last_checked_at)).select_from(FactListing),
        country_code=country_code,
        marketplace_id=marketplace_id,
    )

    updated_24h = int(await db.scalar(updated_stmt) or 0)
    last_update = await db.scalar(last_update_stmt)
    return updated_24h, last_update
