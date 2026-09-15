"""Async grouped reads for geographic pool coverage (service-data, no access-log)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
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


async def read_visible_pool_total(db: AsyncSession) -> int:
    """Grand total of the visible product pool (all countries)."""
    stmt = (
        select(func.count())
        .select_from(FactListing)
        .where(*_visible_product_pool_predicate())
    )
    return int(await db.scalar(stmt) or 0)


MOVERS_WINDOW_HOURS = 24


async def read_world_marketplace_stats(
    db: AsyncSession,
) -> tuple[list[tuple[UUID, Decimal | None, int, int]], Decimal | None, int, int]:
    """World-mode (Zone D) benchmark inputs over the visible product pool.

    Returns (per-marketplace rows, pool avg last_price_eur, pool movers, pool
    total); each row is (marketplace_id, avg_price_eur, movers, count) for the
    ZZ marketplaces. Movers = listings whose price changed within the window;
    rates, never absolutes — global shops differ in size (Zone D decision).
    """
    since = datetime.now(UTC) - timedelta(hours=MOVERS_WINDOW_HOURS)
    movers_case = func.count().filter(FactListing.last_price_changed_at >= since)

    per_mp_stmt = (
        select(
            DimMarketplace.id,
            func.avg(FactListing.last_price_eur).label("avg_price_eur"),
            movers_case.label("movers"),
            func.count().label("listing_count"),
        )
        .select_from(FactListing)
        .join(DimMarketplace, FactListing.marketplace_id == DimMarketplace.id)
        .where(*_visible_product_pool_predicate())
        .where(DimMarketplace.country_code == "ZZ")
        .group_by(DimMarketplace.id)
    )
    pool_stmt = (
        select(
            func.avg(FactListing.last_price_eur).label("avg_price_eur"),
            movers_case.label("movers"),
            func.count().label("listing_count"),
        )
        .select_from(FactListing)
        .where(*_visible_product_pool_predicate())
    )

    per_mp = [
        (
            row.id,
            Decimal(str(row.avg_price_eur)) if row.avg_price_eur is not None else None,
            int(row.movers or 0),
            int(row.listing_count or 0),
        )
        for row in (await db.execute(per_mp_stmt)).all()
    ]
    pool = (await db.execute(pool_stmt)).one()
    pool_avg = Decimal(str(pool.avg_price_eur)) if pool.avg_price_eur is not None else None
    return per_mp, pool_avg, int(pool.movers or 0), int(pool.listing_count or 0)
