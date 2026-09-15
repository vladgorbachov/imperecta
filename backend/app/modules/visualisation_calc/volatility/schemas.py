"""Response schema for the pool price-volatility KPI."""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel


class VolatilityKpi(BaseModel):
    """Average per-listing volatility of daily EUR returns over the window.

    avg_volatility_pct is None until at least one listing has enough daily
    observations — honest empty, never fabricated.
    """

    avg_volatility_pct: Decimal | None
    listings_covered: int
    window_days: int
    period: Literal["7d", "30d", "90d"]
    data_ready: bool
