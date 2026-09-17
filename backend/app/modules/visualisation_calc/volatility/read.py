"""Async SQL-side volatility aggregation over daily EUR price series.

The whole computation (dedupe to the latest scrape per listing per day,
day-over-day pct returns, per-listing sample stddev, cross-listing mean) runs
in one SQL statement returning a single row. The previous implementation
streamed every deduped (listing_id, date_id, price_eur) row into Python and
aggregated there — O(pool x window) transferred rows, which cannot survive the
1.4M-listing pool once list-page price harvesting ramps up.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Literal
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.visualisation_calc.volatility.service import MIN_OBSERVATIONS

_PERIOD_DAYS: dict[str, int] = {
    "7d": 7,
    "30d": 30,
    "90d": 90,
}

# Semantics mirror the former pure-Python calc exactly:
# - latest scrape per (listing, day) wins (DISTINCT ON ... scraped_at DESC);
# - returns are consecutive-point pct changes, pairs with a zero previous
#   price are skipped (the CASE yields NULL, ignored by stddev/count);
# - a listing needs >= MIN_OBSERVATIONS daily points AND >= 2 usable returns;
# - volatility is stddev_samp of returns, the KPI is the mean across listings.
_VOLATILITY_SQL = """
    WITH latest AS (
        SELECT DISTINCT ON (fp.listing_id, fp.date_id)
               fp.listing_id, fp.date_id, fp.price_eur
        FROM fact_price fp
        WHERE fp.date_id >= :min_date_id
          AND fp.date_id <= :max_date_id
          AND fp.price_eur IS NOT NULL
        ORDER BY fp.listing_id, fp.date_id, fp.scraped_at DESC
    ),
    visible AS (
        SELECT l.listing_id, l.date_id, l.price_eur
        FROM latest l
        JOIN fact_listing fl ON fl.id = l.listing_id{country_join}
        WHERE fl.is_active IS TRUE
          AND fl.page_role = 'product'{extra_filters}
    ),
    series AS (
        SELECT listing_id,
               count(*) OVER (PARTITION BY listing_id) AS n_points,
               CASE
                   WHEN lag(price_eur) OVER w <> 0 THEN
                       (price_eur - lag(price_eur) OVER w)
                       / lag(price_eur) OVER w * 100
               END AS ret_pct
        FROM visible
        WINDOW w AS (PARTITION BY listing_id ORDER BY date_id)
    ),
    per_listing AS (
        SELECT stddev_samp(ret_pct) AS vol_pct
        FROM series
        WHERE n_points >= :min_observations
        GROUP BY listing_id
        HAVING count(ret_pct) >= 2
    )
    SELECT avg(vol_pct) AS avg_volatility_pct,
           count(vol_pct) AS listings_covered
    FROM per_listing
"""


def _date_to_date_id(value: date) -> int:
    return value.year * 10_000 + value.month * 100 + value.day


def window_days(period: str) -> int:
    return _PERIOD_DAYS[period]


def _window_date_ids(period: str) -> tuple[int, int]:
    """Inclusive calendar window ending today (UTC), keyed for partition pruning."""
    today = datetime.now(UTC).date()
    start = today - timedelta(days=_PERIOD_DAYS[period])
    return _date_to_date_id(start), _date_to_date_id(today)


async def read_volatility_aggregate(
    db: AsyncSession,
    *,
    period: Literal["7d", "30d", "90d"],
    country_code: str | None,
    marketplace_id: UUID | None,
) -> tuple[Decimal | None, int]:
    """(avg volatility pct across covered listings, covered listing count)."""
    min_date_id, max_date_id = _window_date_ids(period)
    params: dict[str, object] = {
        "min_date_id": min_date_id,
        "max_date_id": max_date_id,
        "min_observations": MIN_OBSERVATIONS,
    }

    country_join = ""
    extra_filters = ""
    if marketplace_id is not None:
        extra_filters += "\n          AND fl.marketplace_id = :marketplace_id"
        params["marketplace_id"] = marketplace_id
    if country_code:
        country_join = (
            "\n        JOIN dim_marketplace dm ON dm.id = fl.marketplace_id"
        )
        extra_filters += "\n          AND dm.country_code = :country_code"
        params["country_code"] = country_code.strip().upper()

    stmt = text(
        _VOLATILITY_SQL.format(
            country_join=country_join,
            extra_filters=extra_filters,
        )
    )
    row = (await db.execute(stmt, params)).one()
    avg = row.avg_volatility_pct
    return (
        Decimal(str(avg)) if avg is not None else None,
        int(row.listings_covered or 0),
    )
