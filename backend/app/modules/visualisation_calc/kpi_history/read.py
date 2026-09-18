"""Async per-day KPI aggregates for dashboard sparklines (P4).

Computed on the fly from fact_price / fact_listing — no rollup table, no
zero-fill: a day with no scrape activity is simply absent from the series
(honest-empty rule). total_pool uses fact_listing.created_at as the pool-entry
day of currently visible listings (current-state flags; documented caveat until
a daily snapshot rollup exists).
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dimensions import DimMarketplace
from app.models.facts import FactListing, FactPrice

CHANGED_THRESHOLD_PCT = Decimal("5.0")


def _date_to_date_id(value: date) -> int:
    return value.year * 10_000 + value.month * 100 + value.day


def _date_from_date_id(date_id: int) -> date:
    return date(date_id // 10_000, date_id // 100 % 100, date_id % 100)


def _visible_product_pool_predicate():
    """Same grain as dashboard KPI / geo-coverage / trend.

    Bare boolean column, NOT ``.is_(True)``: SQLAlchemy renders the latter as
    ``is_active IS TRUE``, and the planner cannot prove that form against the
    ``WHERE is_active = TRUE`` predicate of idx_listing_pool_entry_created —
    the partial index is then skipped and the query seq-scans 1.4M rows
    (verified on prod, 2026-09-18). The bare column renders as ``is_active``
    and matches the index predicate exactly.
    """
    return (
        FactListing.is_active,
        FactListing.page_role == "product",
    )


async def read_daily_price_kpis(
    db: AsyncSession,
    *,
    days: int,
    country_code: str | None,
) -> list[tuple[date, int, int, Decimal | None]]:
    """(day, updated_listings, changed_gt5_listings, avg_abs_change_pct) per
    day that has at least one deduped price row in the window."""
    today = datetime.now(UTC).date()
    start = today - timedelta(days=days - 1)
    min_date_id, max_date_id = _date_to_date_id(start), _date_to_date_id(today)

    ranked = (
        select(
            FactPrice.listing_id,
            FactPrice.date_id,
            FactPrice.price_change_pct,
            func.row_number()
            .over(
                partition_by=[FactPrice.listing_id, FactPrice.date_id],
                order_by=desc(FactPrice.scraped_at),
            )
            .label("rn"),
        )
        .where(
            FactPrice.date_id >= min_date_id,
            FactPrice.date_id <= max_date_id,
        )
    ).subquery("ranked_prices")
    latest = (
        select(ranked.c.listing_id, ranked.c.date_id, ranked.c.price_change_pct).where(
            ranked.c.rn == 1
        )
    ).subquery("latest_daily_prices")

    changed = func.count(latest.c.listing_id).filter(
        func.abs(latest.c.price_change_pct) > CHANGED_THRESHOLD_PCT
    )
    stmt = (
        select(
            latest.c.date_id,
            func.count(latest.c.listing_id).label("updated"),
            changed.label("changed_gt5"),
            func.avg(func.abs(latest.c.price_change_pct)).label("avg_abs_change"),
        )
        .select_from(latest)
        .join(FactListing, FactListing.id == latest.c.listing_id)
        .where(*_visible_product_pool_predicate())
    )
    if country_code:
        stmt = stmt.join(
            DimMarketplace,
            FactListing.marketplace_id == DimMarketplace.id,
        ).where(DimMarketplace.country_code == country_code.strip().upper())
    stmt = stmt.group_by(latest.c.date_id).order_by(latest.c.date_id)

    rows = (await db.execute(stmt)).all()
    return [
        (
            _date_from_date_id(int(row.date_id)),
            int(row.updated or 0),
            int(row.changed_gt5 or 0),
            Decimal(str(row.avg_abs_change)) if row.avg_abs_change is not None else None,
        )
        for row in rows
    ]


async def read_daily_pool_entries(
    db: AsyncSession,
    *,
    days: int,
    country_code: str | None,
) -> tuple[int, list[tuple[date, int]]]:
    """(pool size before the window, per-day new visible listings by created_at)."""
    today = datetime.now(UTC).date()
    start = today - timedelta(days=days - 1)
    start_dt = datetime(start.year, start.month, start.day, tzinfo=UTC)

    def _scoped(stmt):
        stmt = stmt.where(*_visible_product_pool_predicate())
        if country_code:
            stmt = stmt.join(
                DimMarketplace,
                FactListing.marketplace_id == DimMarketplace.id,
            ).where(DimMarketplace.country_code == country_code.strip().upper())
        return stmt

    before = int(
        await db.scalar(
            _scoped(
                select(func.count())
                .select_from(FactListing)
                .where(FactListing.created_at < start_dt)
            )
        )
        or 0
    )

    day_expr = func.date(FactListing.created_at)
    stmt = _scoped(
        select(day_expr.label("day"), func.count().label("added"))
        .select_from(FactListing)
        .where(FactListing.created_at >= start_dt)
    ).group_by(day_expr).order_by(day_expr)
    rows = (await db.execute(stmt)).all()
    return before, [(row.day, int(row.added or 0)) for row in rows]
