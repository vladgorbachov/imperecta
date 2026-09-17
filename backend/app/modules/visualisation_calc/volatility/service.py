"""Pure assembly of the volatility KPI from the SQL-side aggregate.

Volatility per listing = sample standard deviation of day-over-day returns
(pct) of the deduped daily price_eur series; the KPI is the mean across
listings with at least MIN_OBSERVATIONS daily points. The per-listing math
runs in SQL (volatility/read.py) — this layer only rounds and shapes the
response.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

from app.modules.visualisation_calc.volatility.schemas import VolatilityKpi

# Fewer than 3 daily prices gives at most one return — no dispersion to measure.
MIN_OBSERVATIONS = 3

_QUANT = Decimal("0.0001")


def build_volatility_kpi(
    avg_volatility_pct: Decimal | None,
    listings_covered: int,
    *,
    period: Literal["7d", "30d", "90d"],
    window_days: int,
) -> VolatilityKpi:
    """Shape the aggregated volatility read into the KPI response."""
    avg = (
        avg_volatility_pct.quantize(_QUANT, rounding=ROUND_HALF_UP)
        if avg_volatility_pct is not None
        else None
    )
    return VolatilityKpi(
        avg_volatility_pct=avg,
        listings_covered=listings_covered,
        window_days=window_days,
        period=period,
        data_ready=listings_covered > 0,
    )
