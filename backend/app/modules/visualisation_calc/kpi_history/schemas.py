"""Response schema for dashboard KPI history sparklines (P4)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class KpiHistoryPoint(BaseModel):
    date: date
    value: Decimal


class KpiHistorySeries(BaseModel):
    total_pool: list[KpiHistoryPoint]
    updated_24h: list[KpiHistoryPoint]
    changed_gt5: list[KpiHistoryPoint]
    avg_volatility: list[KpiHistoryPoint]


class KpiHistoryResponse(BaseModel):
    """Missing days are absent, never zero-filled (honest-empty rule)."""

    days: int
    series: KpiHistorySeries
