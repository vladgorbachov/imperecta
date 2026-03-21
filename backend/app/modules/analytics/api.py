"""Analytics API endpoints (v2 migration stub)."""

from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Query

from app.common.deps import CurrentUser, DbSession
from app.modules.analytics.schemas import (
    AdvancedSimulationRequest,
    ComparisonResponse,
    PriceHistoryResponse,
    SimulateRequest,
)
from app.modules.analytics.service import BenchmarkService, ForecastService
from app.modules.dashboard.service import DashboardService

router = APIRouter(prefix="/analytics", tags=["analytics"])

_MIG = "Endpoint pending migration to v2 schema"


@router.get("/products/{product_id}/price-history", response_model=PriceHistoryResponse)
async def get_price_history(
    product_id: UUID,
    current_user: CurrentUser,
    db: DbSession,
    period: str = Query("7d", pattern="^(7d|30d|90d)$"),
    competitor_product_id: UUID | None = Query(None),
) -> PriceHistoryResponse:
    _ = db, period, competitor_product_id, product_id, current_user
    return PriceHistoryResponse(
        product_name=_MIG,
        my_price=Decimal("0"),
        competitors=[],
    )


@router.get("/products/{product_id}/comparison", response_model=ComparisonResponse)
async def get_comparison(product_id: UUID, current_user: CurrentUser, db: DbSession) -> ComparisonResponse:
    _ = product_id, current_user, db
    return ComparisonResponse(my_price=Decimal("0"), competitors=[])


@router.get("/products/{product_id}/forecast")
async def get_product_forecast(
    product_id: UUID,
    current_user: CurrentUser,
    db: DbSession,
    days: int = Query(14, ge=1, le=90),
) -> dict:
    return await ForecastService(db, current_user.id).product_forecast(product_id, forecast_days=days)


@router.get("/market-forecast")
async def get_market_forecast(current_user: CurrentUser, db: DbSession, days: int = Query(7, ge=1, le=30)) -> dict:
    return await ForecastService(db, current_user.id).market_forecast(forecast_days=days)


@router.post("/simulate")
async def post_simulate(body: SimulateRequest, current_user: CurrentUser, db: DbSession) -> dict:
    return await ForecastService(db, current_user.id).simulate_scenario(
        body.product_id, body.price_change_pct, body.volume_change_pct
    )


@router.post("/advanced-simulation")
async def post_advanced_simulation(body: AdvancedSimulationRequest, current_user: CurrentUser, db: DbSession) -> dict:
    return await ForecastService(db, current_user.id).advanced_simulation(
        price_change_pct=body.price_change_pct,
        volume_change_pct=body.volume_change_pct,
        ad_budget_change_pct=body.ad_budget_change_pct,
        inflation_pct=body.inflation_pct,
        season=body.season,
    )


@router.get("/competitor-benchmark")
async def get_competitor_benchmark(current_user: CurrentUser, db: DbSession) -> list[dict]:
    return await BenchmarkService(db, current_user.id).get_competitor_scores()


@router.get("/comparison-matrix")
async def get_comparison_matrix(current_user: CurrentUser, db: DbSession) -> dict:
    return await BenchmarkService(db, current_user.id).get_comparison_matrix()


@router.get("/dashboard/summary")
async def get_dashboard_summary(current_user: CurrentUser, db: DbSession) -> dict:
    return await DashboardService(db, current_user.id).get_kpi()


@router.get("/dashboard/anomalies")
async def get_dashboard_anomalies(current_user: CurrentUser, db: DbSession, limit: int = Query(10, ge=1, le=100)) -> dict:
    items = await DashboardService(db, current_user.id).get_anomalies(limit=limit)
    return {"items": items, "message": _MIG}
