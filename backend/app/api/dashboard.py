"""Dashboard API endpoints. KPI, anomalies, aggregate-trend. Market overview uses /api/markets/overview."""

from fastapi import APIRouter, Depends, Query

from app.api.deps import CurrentUser, DbSession
from app.services.dashboard_service import DashboardService

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/kpi")
async def get_kpi(
    current_user: CurrentUser,
    db: DbSession,
) -> dict:
    """Return dashboard KPIs: products, competitors, price changes, alerts, trends."""
    service = DashboardService(db, current_user.id)
    return await service.get_kpi()


@router.get("/anomalies")
async def get_anomalies(
    current_user: CurrentUser,
    db: DbSession,
    limit: int = Query(10, ge=1, le=100, description="Max anomalies to return"),
) -> list[dict]:
    """Return price anomalies (>10% change) in last 24 hours."""
    service = DashboardService(db, current_user.id)
    return await service.get_anomalies(limit=limit)


@router.get("/aggregate-trend")
async def get_aggregate_trend(
    current_user: CurrentUser,
    db: DbSession,
    period: int = Query(30, ge=7, le=90, description="Period in days"),
    forecast: int = Query(7, ge=1, le=30, description="Forecast days"),
) -> dict:
    """Return aggregate price trend: my products vs competitors, with forecast."""
    service = DashboardService(db, current_user.id)
    return await service.get_aggregate_trend(period_days=period, forecast_days=forecast)
