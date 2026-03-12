"""Markets API. Typed responses, no generic dicts."""

from fastapi import APIRouter, Depends, Query

from app.api.deps import CurrentUser, CurrentSuperuser, DbSession
from app.schemas.markets import (
    MarketsCategoryAnalyticsResponse,
    MarketsCommoditiesResponse,
    MarketsCryptoResponse,
    MarketsForexResponse,
    MarketsMarketplaceAnalyticsResponse,
    MarketsOpportunitiesResponse,
    MarketsOverviewResponse,
    MarketsPreferencesResponse,
    MarketsPreferencesUpdate,
    MarketsRefreshMetadataResponse,
    MarketsRefreshStatusItem,
    MarketsTickerResponse,
)
from app.services.markets_service import MarketsService

router = APIRouter(prefix="/markets", tags=["markets"])

OVERVIEW_SORT = ("volatile", "trending", "gainers", "losers", "recent")


@router.get("/preferences", response_model=MarketsPreferencesResponse)
async def get_preferences(
    current_user: CurrentUser,
    db: DbSession,
) -> MarketsPreferencesResponse:
    """Get user markets preferences: preferred country and favorites."""
    service = MarketsService(db, current_user.id)
    data = await service.get_preferences()
    return MarketsPreferencesResponse(**data)


@router.put("/preferences", response_model=MarketsPreferencesResponse)
async def update_preferences(
    body: MarketsPreferencesUpdate,
    current_user: CurrentUser,
    db: DbSession,
) -> MarketsPreferencesResponse:
    """Update preferred country and/or favorite instrument IDs."""
    service = MarketsService(db, current_user.id)
    data = await service.update_preferences(
        preferred_country_code=body.preferred_country_code,
        favorite_instrument_ids=body.favorite_instrument_ids,
    )
    return MarketsPreferencesResponse(**data)


@router.get("/refresh-metadata", response_model=MarketsRefreshMetadataResponse)
async def get_refresh_metadata(
    current_user: CurrentUser,
    db: DbSession,
) -> MarketsRefreshMetadataResponse:
    """Refresh status: last_success, last_failed, provider, country_scope per type."""
    service = MarketsService(db, current_user.id)
    raw = await service.get_refresh_metadata()
    items = [
        MarketsRefreshStatusItem(
            refresh_type=r["refresh_type"],
            last_successful_refresh=r.get("last_successful_refresh"),
            last_failed_refresh=r.get("last_failed_refresh"),
            provider_source=r.get("provider_source"),
            country_scope=r.get("country_scope"),
            error_message=r.get("error_message"),
        )
        for r in raw
    ]
    return MarketsRefreshMetadataResponse(items=items)


@router.get("/forex", response_model=MarketsForexResponse)
async def get_forex(
    current_user: CurrentUser,
    db: DbSession,
) -> MarketsForexResponse:
    """Forex widget data."""
    service = MarketsService(db, current_user.id)
    return MarketsForexResponse(**await service.get_forex())


@router.get("/crypto", response_model=MarketsCryptoResponse)
async def get_crypto(
    current_user: CurrentUser,
    db: DbSession,
) -> MarketsCryptoResponse:
    """Crypto widget data."""
    service = MarketsService(db, current_user.id)
    return MarketsCryptoResponse(**await service.get_crypto())


@router.get("/commodities", response_model=MarketsCommoditiesResponse)
async def get_commodities(
    current_user: CurrentUser,
    db: DbSession,
) -> MarketsCommoditiesResponse:
    """Resources/commodities widget data."""
    service = MarketsService(db, current_user.id)
    return MarketsCommoditiesResponse(**await service.get_commodities())


@router.get("/ticker", response_model=MarketsTickerResponse)
async def get_ticker(
    current_user: CurrentUser,
    db: DbSession,
) -> MarketsTickerResponse:
    """Ticker bar data."""
    service = MarketsService(db, current_user.id)
    return MarketsTickerResponse(**await service.get_ticker())


@router.get("/overview", response_model=MarketsOverviewResponse)
async def get_overview(
    current_user: CurrentUser,
    db: DbSession,
    sort: str = Query(
        "volatile",
        description="Sort: volatile, trending, gainers, losers, recent",
    ),
    limit: int = Query(50, ge=1, le=100, description="Max items"),
) -> MarketsOverviewResponse:
    """Market Overview tabbed table data."""
    if sort not in OVERVIEW_SORT:
        sort = "volatile"
    service = MarketsService(db, current_user.id)
    return MarketsOverviewResponse(**await service.get_overview(sort=sort, limit=limit))


@router.get("/category-analytics", response_model=MarketsCategoryAnalyticsResponse)
async def get_category_analytics(
    current_user: CurrentUser,
    db: DbSession,
) -> MarketsCategoryAnalyticsResponse:
    """Category/segment analytics data."""
    service = MarketsService(db, current_user.id)
    return MarketsCategoryAnalyticsResponse(**await service.get_category_analytics())


@router.get("/marketplace-analytics", response_model=MarketsMarketplaceAnalyticsResponse)
async def get_marketplace_analytics(
    current_user: CurrentUser,
    db: DbSession,
) -> MarketsMarketplaceAnalyticsResponse:
    """Marketplace table analytics. Separate from competitor-benchmark."""
    service = MarketsService(db, current_user.id)
    return MarketsMarketplaceAnalyticsResponse(**await service.get_marketplace_analytics())


@router.get("/opportunities", response_model=MarketsOpportunitiesResponse)
async def get_opportunities(
    current_user: CurrentUser,
    db: DbSession,
) -> MarketsOpportunitiesResponse:
    """Opportunity blocks data."""
    service = MarketsService(db, current_user.id)
    return MarketsOpportunitiesResponse(**await service.get_opportunities())


@router.post("/ingest")
async def trigger_ingest(
    _superuser: CurrentSuperuser,
) -> dict:
    """
    Trigger market data ingestion (forex, crypto, commodities). Superuser only.
    Enqueues Celery task. Does not route through legacy anomalies/benchmark.
    """
    from app.workers.market_data_tasks import ingest_market_data

    task = ingest_market_data.delay()
    return {"status": "enqueued", "task_id": task.id}
