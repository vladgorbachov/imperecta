"""Async grouped reads for geographic pool coverage (service-data, no access-log)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dimensions import DimCountry, DimMarketplace
from app.models.facts import FactListing


def _visible_product_pool_predicate():
    """Same grain as dashboard KPI (slice B): active gated products only."""
    return (
        FactListing.is_active.is_(True),
        FactListing.page_role == "product",
    )


async def read_country_rollup(
    db: AsyncSession,
    *,
    marketplace_id: UUID | None,
) -> list[tuple[str, str, int]]:
    """Return (country_code, country_name, count) for countries with ≥1 visible listing."""
    stmt = (
        select(
            DimMarketplace.country_code,
            DimCountry.name,
            func.count().label("listing_count"),
        )
        .select_from(FactListing)
        .join(DimMarketplace, FactListing.marketplace_id == DimMarketplace.id)
        .join(DimCountry, DimMarketplace.country_code == DimCountry.country_code)
        .where(*_visible_product_pool_predicate())
        .group_by(DimMarketplace.country_code, DimCountry.name)
        .order_by(DimMarketplace.country_code)
    )
    if marketplace_id is not None:
        stmt = stmt.where(FactListing.marketplace_id == marketplace_id)

    result = await db.execute(stmt)
    return [
        (str(row.country_code), str(row.name), int(row.listing_count))
        for row in result.all()
    ]


async def read_marketplace_breakdown(
    db: AsyncSession,
    *,
    country_code: str,
    marketplace_id: UUID | None,
) -> list[tuple[UUID, str, str | None, int]]:
    """Return (marketplace_id, name, domain, count) within a country."""
    normalized_country = country_code.strip().upper()
    stmt = (
        select(
            DimMarketplace.id,
            DimMarketplace.name,
            DimMarketplace.domain,
            func.count().label("listing_count"),
        )
        .select_from(FactListing)
        .join(DimMarketplace, FactListing.marketplace_id == DimMarketplace.id)
        .where(*_visible_product_pool_predicate())
        .where(DimMarketplace.country_code == normalized_country)
        .group_by(DimMarketplace.id, DimMarketplace.name, DimMarketplace.domain)
        .order_by(DimMarketplace.name)
    )
    if marketplace_id is not None:
        stmt = stmt.where(FactListing.marketplace_id == marketplace_id)

    result = await db.execute(stmt)
    return [
        (
            row.id,
            str(row.name),
            row.domain,
            int(row.listing_count),
        )
        for row in result.all()
    ]
