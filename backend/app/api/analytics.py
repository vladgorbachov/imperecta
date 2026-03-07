"""Analytics API endpoints."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, DbSession
from app.models import (
    Alert,
    AlertEvent,
    Competitor,
    CompetitorProduct,
    PriceSnapshot,
    Product,
)
from app.schemas.analytics import (
    AdvancedSimulationRequest,
    ComparisonCompetitor,
    ComparisonResponse,
    PriceHistoryCompetitor,
    PriceHistoryDataPoint,
    PriceHistoryResponse,
    SimulateRequest,
)

router = APIRouter()


@router.get("/products/{product_id}/price-history", response_model=PriceHistoryResponse)
async def get_price_history(
    product_id: UUID,
    current_user: CurrentUser,
    db: DbSession,
    period: str = Query("7d", pattern="^(7d|30d|90d)$"),
    competitor_product_id: UUID | None = Query(None),
) -> PriceHistoryResponse:
    """Get price history for product. Grouping: 7d=each point, 30d=by day, 90d=by week."""

    product_result = await db.execute(
        select(Product.name, Product.current_price).where(
            Product.id == product_id,
            Product.user_id == current_user.id,
        )
    )
    row = product_result.one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    product_name, my_price = row

    now = datetime.now(timezone.utc)
    days = 7 if period == "7d" else (30 if period == "30d" else 90)
    cutoff = now - timedelta(days=days)

    cp_filter = and_(
        CompetitorProduct.product_id == product_id,
        CompetitorProduct.is_active.is_(True),
    )
    if competitor_product_id:
        cp_filter = and_(cp_filter, CompetitorProduct.id == competitor_product_id)

    cps_result = await db.execute(
        select(CompetitorProduct.id, Competitor.name)
        .join(Competitor, CompetitorProduct.competitor_id == Competitor.id)
        .where(cp_filter)
    )
    cps = cps_result.all()

    competitors_data: list[PriceHistoryCompetitor] = []

    for cp_id, comp_name in cps:
        if period == "7d":
            result = await db.execute(
                select(
                    PriceSnapshot.scraped_at,
                    PriceSnapshot.price,
                    PriceSnapshot.promo_label,
                    PriceSnapshot.in_stock,
                )
                .where(
                    PriceSnapshot.competitor_product_id == cp_id,
                    PriceSnapshot.scraped_at >= cutoff,
                )
                .order_by(PriceSnapshot.scraped_at)
            )
            points = [
                PriceHistoryDataPoint(
                    date=r.scraped_at,
                    price=r.price,
                    promo_label=r.promo_label,
                    in_stock=r.in_stock,
                )
                for r in result.all()
            ]
        else:
            agg = func.avg(PriceSnapshot.price).label("avg_price")
            group_col = (
                func.date(PriceSnapshot.scraped_at)
                if period == "30d"
                else func.date_trunc("week", PriceSnapshot.scraped_at)
            )
            result = await db.execute(
                select(
                    group_col.label("dt"),
                    agg,
                    func.max(PriceSnapshot.promo_label).label("promo_label"),
                    func.bool_or(PriceSnapshot.in_stock).label("in_stock"),
                )
                .where(
                    PriceSnapshot.competitor_product_id == cp_id,
                    PriceSnapshot.scraped_at >= cutoff,
                )
                .group_by(group_col)
                .order_by(group_col)
            )
            points = [
                PriceHistoryDataPoint(
                    date=r.dt,
                    price=r.avg_price,
                    promo_label=r.promo_label,
                    in_stock=r.in_stock,
                )
                for r in result.all()
            ]

        competitors_data.append(
            PriceHistoryCompetitor(
                competitor_name=comp_name,
                competitor_product_id=cp_id,
                data_points=points,
            )
        )

    return PriceHistoryResponse(
        product_name=product_name,
        my_price=my_price,
        competitors=competitors_data,
    )


@router.get("/products/{product_id}/comparison", response_model=ComparisonResponse)
async def get_comparison(
    product_id: UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> ComparisonResponse:
    """Current price comparison: my price vs all competitors. Trend vs 7 days ago."""

    product_result = await db.execute(
        select(Product.name, Product.current_price).where(
            Product.id == product_id,
            Product.user_id == current_user.id,
        )
    )
    row = product_result.one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    _, my_price = row

    week_ago = datetime.now(timezone.utc) - timedelta(days=7)

    cps_result = await db.execute(
        select(
            CompetitorProduct.id,
            Competitor.name,
            CompetitorProduct.last_price,
            CompetitorProduct.last_promo_label,
            CompetitorProduct.last_in_stock,
        )
        .join(Competitor, CompetitorProduct.competitor_id == Competitor.id)
        .where(
            CompetitorProduct.product_id == product_id,
            CompetitorProduct.is_active.is_(True),
        )
    )
    cps = cps_result.all()

    competitors: list[ComparisonCompetitor] = []
    for cp_id, comp_name, last_price, promo_label, in_stock in cps:
        price_7d_ago = None
        price_7d_result = await db.execute(
            select(PriceSnapshot.price)
            .where(
                PriceSnapshot.competitor_product_id == cp_id,
                PriceSnapshot.scraped_at <= week_ago,
            )
            .order_by(PriceSnapshot.scraped_at.desc())
            .limit(1)
        )
        r7 = price_7d_result.scalar_one_or_none()
        if r7:
            price_7d_ago = r7[0]

        if last_price and price_7d_ago and price_7d_ago > 0:
            if last_price > price_7d_ago:
                trend = "up"
            elif last_price < price_7d_ago:
                trend = "down"
            else:
                trend = "stable"
        else:
            trend = "stable"

        diff_amount = None
        diff_percent = None
        if last_price is not None and my_price > 0:
            diff_amount = last_price - my_price
            diff_percent = float((last_price - my_price) / my_price * 100)

        competitors.append(
            ComparisonCompetitor(
                name=comp_name,
                price=last_price,
                diff_amount=diff_amount,
                diff_percent=round(diff_percent, 2) if diff_percent is not None else None,
                promo_label=promo_label,
                in_stock=in_stock,
                trend=trend,
            )
        )

    return ComparisonResponse(my_price=my_price, competitors=competitors)


# --- Forecast and simulation endpoints ---


@router.get("/products/{product_id}/forecast")
async def get_product_forecast(
    product_id: UUID,
    current_user: CurrentUser,
    db: DbSession,
    days: int = Query(14, ge=1, le=90, description="Forecast horizon in days"),
) -> dict:
    """Forecast price trend for a product based on competitor price history."""
    from app.services.forecast_service import ForecastService

    service = ForecastService(db, current_user.id)
    try:
        return await service.product_forecast(product_id, forecast_days=days)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.get("/market-forecast")
async def get_market_forecast(
    current_user: CurrentUser,
    db: DbSession,
    days: int = Query(7, ge=1, le=30, description="Forecast horizon in days"),
) -> dict:
    """Aggregate market forecast across all user's products."""
    from app.services.forecast_service import ForecastService

    service = ForecastService(db, current_user.id)
    return await service.market_forecast(forecast_days=days)


@router.post("/simulate")
async def post_simulate(
    body: SimulateRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> dict:
    """Simulate price change impact on sales, revenue, and margin."""
    from app.services.forecast_service import ForecastService

    service = ForecastService(db, current_user.id)
    return await service.simulate_scenario(
        product_id=body.product_id,
        price_change_pct=body.price_change_pct,
        volume_change_pct=body.volume_change_pct,
    )


@router.post("/advanced-simulation")
async def post_advanced_simulation(
    body: AdvancedSimulationRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> dict:
    """Extended simulation with season, ad budget, and inflation factors."""
    from app.services.forecast_service import ForecastService

    service = ForecastService(db, current_user.id)
    return await service.advanced_simulation(
        price_change_pct=body.price_change_pct,
        volume_change_pct=body.volume_change_pct,
        ad_budget_change_pct=body.ad_budget_change_pct,
        inflation_pct=body.inflation_pct,
        season=body.season,
    )


@router.get("/competitor-benchmark")
async def get_competitor_benchmark(
    current_user: CurrentUser,
    db: DbSession,
) -> list[dict]:
    """Competitor benchmark scores (0-100) with components and trend."""
    from app.services.benchmark_service import BenchmarkService

    service = BenchmarkService(db, current_user.id)
    return await service.get_competitor_scores()


@router.get("/comparison-matrix")
async def get_comparison_matrix(
    current_user: CurrentUser,
    db: DbSession,
) -> dict:
    """Price comparison matrix: products × competitors (% diff, positive = I'm cheaper)."""
    from app.services.benchmark_service import BenchmarkService

    service = BenchmarkService(db, current_user.id)
    return await service.get_comparison_matrix()


# --- Dashboard endpoints (frontend expects /api/analytics/dashboard/...) ---


@router.get("/dashboard/summary")
async def get_dashboard_summary(
    current_user: CurrentUser,
    db: DbSession,
) -> dict:
    """Dashboard summary: KPIs, price changes, top changes, active promos."""
    from app.services.dashboard_service import DashboardService

    service = DashboardService(db, current_user.id)
    return await service.get_dashboard_summary()


@router.get("/dashboard/anomalies")
async def get_dashboard_anomalies(
    current_user: CurrentUser,
    db: DbSession,
    limit: int = Query(10, ge=1, le=100, description="Max anomalies to return"),
) -> dict:
    """Price anomalies (>10% change) in last 24 hours. Returns { items: [...] }."""
    from app.services.dashboard_service import DashboardService

    service = DashboardService(db, current_user.id)
    items = await service.get_anomalies(limit=limit)
    return {"items": items}
