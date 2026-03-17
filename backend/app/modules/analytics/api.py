"""Analytics API endpoints."""

from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import and_, select

from app.common.deps import CurrentUser, DbSession
from app.models import Competitor, CompetitorProduct, PriceSnapshot, Product
from app.modules.analytics.schemas import (
    AdvancedSimulationRequest,
    ComparisonCompetitor,
    ComparisonResponse,
    PriceHistoryCompetitor,
    PriceHistoryDataPoint,
    PriceHistoryResponse,
    SimulateRequest,
)
from app.modules.analytics.service import BenchmarkService, ForecastService
from app.modules.dashboard.service import DashboardService

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/products/{product_id}/price-history", response_model=PriceHistoryResponse)
async def get_price_history(
    product_id: UUID,
    current_user: CurrentUser,
    db: DbSession,
    period: str = Query("7d", pattern="^(7d|30d|90d)$"),
    competitor_product_id: UUID | None = Query(None),
) -> PriceHistoryResponse:
    product_result = await db.execute(select(Product.name, Product.current_price).where(Product.id == product_id, Product.user_id == current_user.id))
    row = product_result.one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    product_name, my_price = row
    now = datetime.now(timezone.utc)
    days = 7 if period == "7d" else (30 if period == "30d" else 90)
    cutoff = now - timedelta(days=days)
    cp_filter = and_(CompetitorProduct.product_id == product_id, CompetitorProduct.is_active.is_(True))
    if competitor_product_id:
        cp_filter = and_(cp_filter, CompetitorProduct.id == competitor_product_id)
    cps_result = await db.execute(select(CompetitorProduct.id, Competitor.name).join(Competitor, CompetitorProduct.competitor_id == Competitor.id).where(cp_filter))
    cps = cps_result.all()
    competitors_data: list[PriceHistoryCompetitor] = []
    for cp_id, comp_name in cps:
        result = await db.execute(
            select(PriceSnapshot.scraped_at, PriceSnapshot.price, PriceSnapshot.promo_label, PriceSnapshot.in_stock)
            .where(PriceSnapshot.competitor_product_id == cp_id, PriceSnapshot.scraped_at >= cutoff)
            .order_by(PriceSnapshot.scraped_at)
        )
        points = [PriceHistoryDataPoint(date=r.scraped_at, price=r.price, promo_label=r.promo_label, in_stock=r.in_stock) for r in result.all()]
        competitors_data.append(PriceHistoryCompetitor(competitor_name=comp_name, competitor_product_id=cp_id, data_points=points))
    return PriceHistoryResponse(product_name=product_name, my_price=my_price, competitors=competitors_data)


@router.get("/products/{product_id}/comparison", response_model=ComparisonResponse)
async def get_comparison(product_id: UUID, current_user: CurrentUser, db: DbSession) -> ComparisonResponse:
    product_result = await db.execute(select(Product.name, Product.current_price).where(Product.id == product_id, Product.user_id == current_user.id))
    row = product_result.one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    _, my_price = row
    cps_result = await db.execute(
        select(Competitor.name, CompetitorProduct.last_price, CompetitorProduct.last_promo_label, CompetitorProduct.last_in_stock)
        .join(Competitor, CompetitorProduct.competitor_id == Competitor.id)
        .where(CompetitorProduct.product_id == product_id, CompetitorProduct.is_active.is_(True))
    )
    competitors = []
    for comp_name, last_price, promo_label, in_stock in cps_result.all():
        diff_amount = (last_price - my_price) if last_price is not None else None
        diff_percent = float((last_price - my_price) / my_price * 100) if last_price is not None and my_price > 0 else None
        competitors.append(
            ComparisonCompetitor(
                name=comp_name,
                price=last_price,
                diff_amount=diff_amount,
                diff_percent=round(diff_percent, 2) if diff_percent is not None else None,
                promo_label=promo_label,
                in_stock=in_stock,
                trend="stable",
            )
        )
    return ComparisonResponse(my_price=my_price, competitors=competitors)


@router.get("/products/{product_id}/forecast")
async def get_product_forecast(product_id: UUID, current_user: CurrentUser, db: DbSession, days: int = Query(14, ge=1, le=90)) -> dict:
    service = ForecastService(db, current_user.id)
    try:
        return await service.product_forecast(product_id, forecast_days=days)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error))


@router.get("/market-forecast")
async def get_market_forecast(current_user: CurrentUser, db: DbSession, days: int = Query(7, ge=1, le=30)) -> dict:
    return await ForecastService(db, current_user.id).market_forecast(forecast_days=days)


@router.post("/simulate")
async def post_simulate(body: SimulateRequest, current_user: CurrentUser, db: DbSession) -> dict:
    return await ForecastService(db, current_user.id).simulate_scenario(body.product_id, body.price_change_pct, body.volume_change_pct)


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
    return await DashboardService(db, current_user.id).get_dashboard_summary()


@router.get("/dashboard/anomalies")
async def get_dashboard_anomalies(current_user: CurrentUser, db: DbSession, limit: int = Query(10, ge=1, le=100)) -> dict:
    items = await DashboardService(db, current_user.id).get_anomalies(limit=limit)
    return {"items": items}
