"""Dashboard API endpoints."""

from uuid import UUID

from fastapi import APIRouter, Query

from app.common.deps import CurrentUser, DbSession
from app.modules.dashboard.schemas import (
    MarketsCategoryAnalyticsResponse,
    MarketsMarketplaceAnalyticsResponse,
    MarketsOpportunitiesResponse,
)
from app.modules.dashboard.service import DashboardService
from app.modules.market_data.service import MarketsService
from app.modules.product_pool.service import ProductPoolService

dashboard_router = APIRouter(prefix="/dashboard", tags=["dashboard"])
markets_dashboard_router = APIRouter(prefix="/markets", tags=["markets"])
router = APIRouter()
OVERVIEW_SORT = ("volatile", "trending", "gainers", "losers", "recent")


@dashboard_router.get("/kpi")
async def get_kpi(current_user: CurrentUser, db: DbSession) -> dict:
    service = DashboardService(db, current_user.id)
    return await service.get_kpi()


@dashboard_router.get("/anomalies")
async def get_anomalies(
    current_user: CurrentUser,
    db: DbSession,
    limit: int = Query(10, ge=1, le=100, description="Max anomalies to return"),
) -> list[dict]:
    service = DashboardService(db, current_user.id)
    return await service.get_anomalies(limit=limit)


@dashboard_router.get("/aggregate-trend")
async def get_aggregate_trend(
    current_user: CurrentUser,
    db: DbSession,
    period: int = Query(30, ge=7, le=90, description="Period in days"),
    forecast: int = Query(7, ge=1, le=30, description="Forecast days"),
) -> dict:
    service = DashboardService(db, current_user.id)
    return await service.get_aggregate_trend(period_days=period, forecast_days=forecast)


@markets_dashboard_router.get("/overview")
async def get_overview(
    current_user: CurrentUser,
    db: DbSession,
    sort: str = Query("volatile", description="Sort: volatile, trending, gainers, losers, recent"),
    search: str | None = Query(None, min_length=2),
    marketplace_id: UUID | None = Query(None),
    limit: int = Query(50, ge=1, le=500, description="Max items per page"),
    offset: int = Query(0, ge=0),
) -> dict:
    if sort not in OVERVIEW_SORT:
        sort = "volatile"
    _ = current_user
    service = ProductPoolService(db)
    items, total = await service.list_products(
        sort=sort,
        search=search,
        marketplace_id=marketplace_id,
        limit=limit,
        offset=offset,
    )
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@markets_dashboard_router.get("/category-analytics", response_model=MarketsCategoryAnalyticsResponse)
async def get_category_analytics(current_user: CurrentUser, db: DbSession) -> MarketsCategoryAnalyticsResponse:
    service = MarketsService(db, current_user.id)
    return MarketsCategoryAnalyticsResponse(**await service.get_category_analytics())


@markets_dashboard_router.get("/marketplace-analytics", response_model=MarketsMarketplaceAnalyticsResponse)
async def get_marketplace_analytics(
    current_user: CurrentUser,
    db: DbSession,
) -> MarketsMarketplaceAnalyticsResponse:
    service = MarketsService(db, current_user.id)
    return MarketsMarketplaceAnalyticsResponse(**await service.get_marketplace_analytics())


@markets_dashboard_router.get("/opportunities", response_model=MarketsOpportunitiesResponse)
async def get_opportunities(current_user: CurrentUser, db: DbSession) -> MarketsOpportunitiesResponse:
    service = MarketsService(db, current_user.id)
    return MarketsOpportunitiesResponse(**await service.get_opportunities())


router.include_router(dashboard_router)
router.include_router(markets_dashboard_router)
