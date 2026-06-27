"""Async grouped read for EUR-normalized average price trend."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Literal
from uuid import UUID

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

from app.models.dimensions import DimDate, DimMarketplace
from app.models.facts import FactListing, FactPrice

_PERIOD_DAYS: dict[str, int] = {
    "7d": 7,
    "30d": 30,
    "90d": 90,
}


def _date_to_date_id(value: date) -> int:
    return value.year * 10_000 + value.month * 100 + value.day


def _window_date_ids(period: str) -> tuple[int, int]:
    """Inclusive calendar window ending today (UTC), keyed for partition pruning."""
    today = datetime.now(UTC).date()
    start = today - timedelta(days=_PERIOD_DAYS[period])
    return _date_to_date_id(start), _date_to_date_id(today)


def _visible_product_pool_predicate():
    """Same grain as dashboard KPI / geo-coverage (slice B)."""
    return (
        FactListing.is_active.is_(True),
        FactListing.page_role == "product",
    )


def _deduped_daily_prices_subquery(min_date_id: int, max_date_id: int):
    """Latest fact_price row per (listing_id, date_id) by scraped_at within the window."""
    ranked = (
        select(
            FactPrice.listing_id,
            FactPrice.date_id,
            FactPrice.price_eur,
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

    return (
        select(
            ranked.c.listing_id,
            ranked.c.date_id,
            ranked.c.price_eur,
        ).where(ranked.c.rn == 1)
    ).subquery("latest_daily_prices")


def _apply_trend_scope(
    stmt: Select,
    *,
    country_code: str | None,
    marketplace_id: UUID | None,
) -> Select:
    """Mirror kpi/read._apply_dashboard_kpi_filters entity scope."""
    stmt = stmt.where(*_visible_product_pool_predicate())
    if marketplace_id is not None:
        stmt = stmt.where(FactListing.marketplace_id == marketplace_id)
    if country_code:
        stmt = stmt.join(
            DimMarketplace,
            FactListing.marketplace_id == DimMarketplace.id,
        ).where(DimMarketplace.country_code == country_code.strip().upper())
    return stmt


async def read_price_trend(
    db: AsyncSession,
    *,
    period: Literal["7d", "30d", "90d"],
    bucket: Literal["day", "week", "month"],
    country_code: str | None,
    marketplace_id: UUID | None,
) -> list[tuple[date, Decimal | None, int]]:
    """Return (bucket_start, avg_price_eur, sample_size) ordered ascending."""
    min_date_id, max_date_id = _window_date_ids(period)
    latest = _deduped_daily_prices_subquery(min_date_id, max_date_id)

    if bucket == "day":
        group_by = (DimDate.date_id, DimDate.full_date)
        bucket_start_expr = DimDate.full_date
        order_by = (DimDate.full_date,)
    elif bucket == "week":
        group_by = (DimDate.year, DimDate.week_iso)
        bucket_start_expr = func.min(DimDate.full_date)
        order_by = (DimDate.year, DimDate.week_iso)
    else:
        group_by = (DimDate.year, DimDate.month)
        bucket_start_expr = func.min(DimDate.full_date)
        order_by = (DimDate.year, DimDate.month)

    stmt = (
        select(
            bucket_start_expr.label("bucket_start"),
            func.avg(latest.c.price_eur).label("avg_price_eur"),
            func.count(latest.c.price_eur).label("sample_size"),
        )
        .select_from(latest)
        .join(FactListing, FactListing.id == latest.c.listing_id)
        .join(DimDate, DimDate.date_id == latest.c.date_id)
    )
    stmt = _apply_trend_scope(
        stmt,
        country_code=country_code,
        marketplace_id=marketplace_id,
    )
    stmt = stmt.group_by(*group_by).order_by(*order_by)

    result = await db.execute(stmt)
    rows: list[tuple[date, Decimal | None, int]] = []
    for row in result.all():
        avg_value = row.avg_price_eur
        rows.append(
            (
                row.bucket_start,
                Decimal(str(avg_value)) if avg_value is not None else None,
                int(row.sample_size or 0),
            ),
        )
    return rows
