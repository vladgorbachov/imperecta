"""Pure volatility computation over per-listing daily EUR price series.

Volatility per listing = sample standard deviation of day-over-day returns
(pct) of the deduped daily price_eur series; the KPI is the mean across
listings with at least MIN_OBSERVATIONS daily points. Replaces the old proxy
(mean |last price_change_pct| from movements.summary) with a real dispersion
measure over the window.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Literal
from uuid import UUID

from app.modules.visualisation_calc.volatility.schemas import VolatilityKpi

# Fewer than 3 daily prices gives at most one return — no dispersion to measure.
MIN_OBSERVATIONS = 3

_QUANT = Decimal("0.0001")


def _listing_volatility_pct(prices: list[Decimal]) -> Decimal | None:
    """Sample stddev of day-over-day pct returns; None when undefined."""
    if len(prices) < MIN_OBSERVATIONS:
        return None
    returns: list[Decimal] = []
    for prev, cur in zip(prices, prices[1:], strict=False):
        if prev == 0:
            continue
        returns.append((cur - prev) / prev * Decimal(100))
    if len(returns) < 2:
        return None
    mean = sum(returns) / Decimal(len(returns))
    variance = sum((r - mean) ** 2 for r in returns) / Decimal(len(returns) - 1)
    return variance.sqrt()


def build_volatility_kpi(
    rows: list[tuple[UUID, int, Decimal]],
    *,
    period: Literal["7d", "30d", "90d"],
    window_days: int,
) -> VolatilityKpi:
    """Aggregate per-listing volatilities; rows come ordered by (listing, day)."""
    per_listing: dict[UUID, list[Decimal]] = {}
    for listing_id, _date_id, price_eur in rows:
        per_listing.setdefault(listing_id, []).append(price_eur)

    volatilities = [
        vol
        for prices in per_listing.values()
        if (vol := _listing_volatility_pct(prices)) is not None
    ]
    if volatilities:
        avg = (sum(volatilities) / Decimal(len(volatilities))).quantize(
            _QUANT, rounding=ROUND_HALF_UP
        )
    else:
        avg = None
    return VolatilityKpi(
        avg_volatility_pct=avg,
        listings_covered=len(volatilities),
        window_days=window_days,
        period=period,
        data_ready=bool(volatilities),
    )
