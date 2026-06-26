"""Compute KPI aggregates: total pool, updated-in-24h, last-update."""

from __future__ import annotations

from datetime import datetime

from app.modules.visualisation_calc.kpi.schemas import DashboardKpi


def build_dashboard_kpi(
    updated_24h: int,
    last_update: datetime | None,
) -> DashboardKpi:
    """Pack read scalars into the dashboard KPI response (pure, no DB)."""
    return DashboardKpi(updated_24h=updated_24h, last_update=last_update)
