"""Async read of per-listing daily EUR price series for volatility calc."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Literal
from uuid import UUID

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dimensions import DimMarketplace
from app.models.facts import FactListing, FactPrice

_PERIOD_DAYS: dict[str, int] = {
    "7d": 7,
    "30d": 30,
    "90d": 90,
}


def _date_to_date_id(value: date) -> int:
    return value.year * 10_000 + value.month * 100 + value.day


def window_days(period: str) -> int:
    return _PERIOD_DAYS[period]


def _window_date_ids(period: str) -> tuple[int, int]:
    """Inclusive calendar window ending today (UTC), keyed for partition pruning."""
    today = datetime.now(UTC).date()
    start = today - timedelta(days=_PERIOD_DAYS[period])
    return _date_to_date_id(start), _date_to_date_id(today)


async def read_daily_price_series(
    db: AsyncSession,
    *,
    period: Literal["7d", "30d", "90d"],
    country_code: str | None,
    marketplace_id: UUID | None,
) -> list[tuple[UUID, int, Decimal]]:
    """(listing_id, date_id, price_eur) rows, deduped to the latest scrape per
    listing per day, visible-product grain, ordered for per-listing grouping."""
    min_date_id, max_date_id = _window_date_ids(period)

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
            FactPrice.price_eur.is_not(None),
        )
    ).subquery("ranked_prices")

    latest = (
        select(ranked.c.listing_id, ranked.c.date_id, ranked.c.price_eur).where(
            ranked.c.rn == 1
        )
    ).subquery("latest_daily_prices")

    stmt = (
        select(latest.c.listing_id, latest.c.date_id, latest.c.price_eur)
        .select_from(latest)
        .join(FactListing, FactListing.id == latest.c.listing_id)
        .where(
            FactListing.is_active.is_(True),
            FactListing.page_role == "product",
        )
    )
    if marketplace_id is not None:
        stmt = stmt.where(FactListing.marketplace_id == marketplace_id)
    if country_code:
        stmt = stmt.join(
            DimMarketplace,
            FactListing.marketplace_id == DimMarketplace.id,
        ).where(DimMarketplace.country_code == country_code.strip().upper())
    stmt = stmt.order_by(latest.c.listing_id, latest.c.date_id)

    result = await db.execute(stmt)
    return [
        (row.listing_id, int(row.date_id), Decimal(str(row.price_eur)))
        for row in result.all()
    ]
