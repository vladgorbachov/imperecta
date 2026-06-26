"""Response schemas for dashboard KPI aggregates."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class DashboardKpi(BaseModel):
    """Pool freshness KPIs: listings checked in 24h and latest check timestamp."""

    updated_24h: int
    last_update: datetime | None = None
