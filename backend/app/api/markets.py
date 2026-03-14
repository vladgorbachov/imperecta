"""Markets API. Typed responses, no generic dicts."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import CurrentUser, CurrentSuperuser, DbSession
from app.services.market_data_service import (
    fetch_commodities,
    fetch_crypto_prices,
    fetch_forex_rates,
    get_fuel_prices,
    get_ticker_data,
)

# Europe + CIS countries only. Alphabetical by English name.
COUNTRIES = [
    {"code": "AM", "name": "Armenia", "name_local": "Армения", "flag": "🇦🇲", "region": "cis"},
    {"code": "AZ", "name": "Azerbaijan", "name_local": "Азербайджан", "flag": "🇦🇿", "region": "cis"},
    {"code": "BY", "name": "Belarus", "name_local": "Беларусь", "flag": "🇧🇾", "region": "cis"},
    {"code": "GE", "name": "Georgia", "name_local": "Грузия", "flag": "🇬🇪", "region": "cis"},
    {"code": "KZ", "name": "Kazakhstan", "name_local": "Казахстан", "flag": "🇰🇿", "region": "cis"},
    {"code": "KG", "name": "Kyrgyzstan", "name_local": "Кыргызстан", "flag": "🇰🇬", "region": "cis"},
    {"code": "MD", "name": "Moldova", "name_local": "Молдова", "flag": "🇲🇩", "region": "cis"},
    {"code": "RU", "name": "Russia", "name_local": "Россия", "flag": "🇷🇺", "region": "cis"},
    {"code": "TJ", "name": "Tajikistan", "name_local": "Таджикистан", "flag": "🇹🇯", "region": "cis"},
    {"code": "TM", "name": "Turkmenistan", "name_local": "Туркменистан", "flag": "🇹🇲", "region": "cis"},
    {"code": "UA", "name": "Ukraine", "name_local": "Украина", "flag": "🇺🇦", "region": "cis"},
    {"code": "UZ", "name": "Uzbekistan", "name_local": "Узбекистан", "flag": "🇺🇿", "region": "cis"},
    {"code": "AL", "name": "Albania", "name_local": "Албания", "flag": "🇦🇱", "region": "europe"},
    {"code": "AD", "name": "Andorra", "name_local": "Андорра", "flag": "🇦🇩", "region": "europe"},
    {"code": "AT", "name": "Austria", "name_local": "Австрия", "flag": "🇦🇹", "region": "europe"},
    {"code": "BE", "name": "Belgium", "name_local": "Бельгия", "flag": "🇧🇪", "region": "europe"},
    {"code": "BA", "name": "Bosnia and Herzegovina", "name_local": "Босния", "flag": "🇧🇦", "region": "europe"},
    {"code": "BG", "name": "Bulgaria", "name_local": "Болгария", "flag": "🇧🇬", "region": "europe"},
    {"code": "HR", "name": "Croatia", "name_local": "Хорватия", "flag": "🇭🇷", "region": "europe"},
    {"code": "CY", "name": "Cyprus", "name_local": "Кипр", "flag": "🇨🇾", "region": "europe"},
    {"code": "CZ", "name": "Czech Republic", "name_local": "Чехия", "flag": "🇨🇿", "region": "europe"},
    {"code": "DK", "name": "Denmark", "name_local": "Дания", "flag": "🇩🇰", "region": "europe"},
    {"code": "EE", "name": "Estonia", "name_local": "Эстония", "flag": "🇪🇪", "region": "europe"},
    {"code": "FI", "name": "Finland", "name_local": "Финляндия", "flag": "🇫🇮", "region": "europe"},
    {"code": "FR", "name": "France", "name_local": "Франция", "flag": "🇫🇷", "region": "europe"},
    {"code": "DE", "name": "Germany", "name_local": "Германия", "flag": "🇩🇪", "region": "europe"},
    {"code": "GR", "name": "Greece", "name_local": "Греция", "flag": "🇬🇷", "region": "europe"},
    {"code": "HU", "name": "Hungary", "name_local": "Венгрия", "flag": "🇭🇺", "region": "europe"},
    {"code": "IS", "name": "Iceland", "name_local": "Исландия", "flag": "🇮🇸", "region": "europe"},
    {"code": "IE", "name": "Ireland", "name_local": "Ирландия", "flag": "🇮🇪", "region": "europe"},
    {"code": "IT", "name": "Italy", "name_local": "Италия", "flag": "🇮🇹", "region": "europe"},
    {"code": "XK", "name": "Kosovo", "name_local": "Косово", "flag": "🇽🇰", "region": "europe"},
    {"code": "LV", "name": "Latvia", "name_local": "Латвия", "flag": "🇱🇻", "region": "europe"},
    {"code": "LI", "name": "Liechtenstein", "name_local": "Лихтенштейн", "flag": "🇱🇮", "region": "europe"},
    {"code": "LT", "name": "Lithuania", "name_local": "Литва", "flag": "🇱🇹", "region": "europe"},
    {"code": "LU", "name": "Luxembourg", "name_local": "Люксембург", "flag": "🇱🇺", "region": "europe"},
    {"code": "MT", "name": "Malta", "name_local": "Мальта", "flag": "🇲🇹", "region": "europe"},
    {"code": "ME", "name": "Montenegro", "name_local": "Черногория", "flag": "🇲🇪", "region": "europe"},
    {"code": "NL", "name": "Netherlands", "name_local": "Нидерланды", "flag": "🇳🇱", "region": "europe"},
    {"code": "MK", "name": "North Macedonia", "name_local": "Сев. Македония", "flag": "🇲🇰", "region": "europe"},
    {"code": "NO", "name": "Norway", "name_local": "Норвегия", "flag": "🇳🇴", "region": "europe"},
    {"code": "PL", "name": "Poland", "name_local": "Польша", "flag": "🇵🇱", "region": "europe"},
    {"code": "PT", "name": "Portugal", "name_local": "Португалия", "flag": "🇵🇹", "region": "europe"},
    {"code": "RO", "name": "Romania", "name_local": "Румыния", "flag": "🇷🇴", "region": "europe"},
    {"code": "RS", "name": "Serbia", "name_local": "Сербия", "flag": "🇷🇸", "region": "europe"},
    {"code": "SK", "name": "Slovakia", "name_local": "Словакия", "flag": "🇸🇰", "region": "europe"},
    {"code": "SI", "name": "Slovenia", "name_local": "Словения", "flag": "🇸🇮", "region": "europe"},
    {"code": "ES", "name": "Spain", "name_local": "Испания", "flag": "🇪🇸", "region": "europe"},
    {"code": "SE", "name": "Sweden", "name_local": "Швеция", "flag": "🇸🇪", "region": "europe"},
    {"code": "CH", "name": "Switzerland", "name_local": "Швейцария", "flag": "🇨🇭", "region": "europe"},
    {"code": "TR", "name": "Turkey", "name_local": "Турция", "flag": "🇹🇷", "region": "europe"},
    {"code": "GB", "name": "United Kingdom", "name_local": "Великобритания", "flag": "🇬🇧", "region": "europe"},
]
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


@router.get("/countries")
async def get_countries(
    current_user: CurrentUser,
) -> list[dict]:
    """
    Countries list: Europe + CIS only.
    Meta options (Europe, CIS) first, separator, then countries alphabetically.
    """
    meta = [
        {"code": "EUROPE", "name": "Europe", "name_local": "Европа", "flag": "🇪🇺", "region": "meta", "is_region": True},
        {"code": "CIS", "name": "CIS", "name_local": "СНГ", "flag": "🌍", "region": "meta", "is_region": True},
        {"separator": True},
    ]
    return meta + COUNTRIES


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


def _now() -> datetime:
    return datetime.now(timezone.utc)


@router.get("/forex", response_model=MarketsForexResponse)
async def get_forex(current_user: CurrentUser) -> MarketsForexResponse:
    """Forex widget data from ExchangeRate-API."""
    raw = await fetch_forex_rates("EUR")
    if not raw:
        raise HTTPException(503, "Forex data temporarily unavailable")
    now = _now()
    items = [
        {
            "symbol": p["pair"],
            "bid": p["rate"],
            "ask": p["rate"],
            "spread": 0,
            "change_24h": p.get("change_24h"),
            "refreshed_at": now,
        }
        for p in raw
    ]
    return MarketsForexResponse(items=items, last_refreshed_at=now)


@router.get("/crypto", response_model=MarketsCryptoResponse)
async def get_crypto(current_user: CurrentUser) -> MarketsCryptoResponse:
    """Crypto widget data from CoinGecko. Never 503 — returns 200 with items=[], error on API failure."""
    now = _now()
    try:
        raw, from_cache = await fetch_crypto_prices()
        items = [
            {
                "symbol": c["symbol"],
                "price": c["price"],
                "change_24h": c.get("change_24h"),
                "market_cap": c.get("market_cap"),
                "refreshed_at": now,
            }
            for c in raw
        ]
        return MarketsCryptoResponse(
            items=items,
            error=None,
            cached=from_cache,
            last_refreshed_at=now,
        )
    except Exception:
        return MarketsCryptoResponse(
            items=[],
            error="CoinGecko API rate limited (429). Retry in 2 hours.",
            cached=False,
            last_refreshed_at=now,
        )


@router.get("/commodities", response_model=MarketsCommoditiesResponse)
async def get_commodities(current_user: CurrentUser) -> MarketsCommoditiesResponse:
    """Resources/commodities widget data from metals.dev + static oil/gas/fuel. Never 503."""
    now = _now()
    try:
        raw = await fetch_commodities()
        items = [
            {
                "symbol": c["symbol"],
                "name": c.get("name"),
                "price": c["price"],
                "change_24h": c.get("change_24h"),
                "unit": c.get("unit"),
                "refreshed_at": now,
            }
            for c in raw
        ]
        return MarketsCommoditiesResponse(
            items=items,
            error=None,
            cached=False,
            last_refreshed_at=now,
        )
    except Exception:
        return MarketsCommoditiesResponse(
            items=[],
            error="Metals API unauthorized (401). Check API key.",
            cached=False,
            last_refreshed_at=now,
        )


@router.get("/fuel")
async def get_fuel(
    current_user: CurrentUser,
    country: str = Query("UA", description="Country code or EUROPE/CIS"),
) -> dict:
    """Fuel prices for a country or region."""
    data = await get_fuel_prices(country)
    if not data:
        raise HTTPException(404, f"No fuel data for country: {country}")
    return data


@router.get("/ticker", response_model=MarketsTickerResponse)
async def get_ticker(
    current_user: CurrentUser,
    country: str = Query("UA", description="Country code for fuel data"),
) -> MarketsTickerResponse:
    """Ticker bar data: forex + crypto + commodities + fuel."""
    raw = await get_ticker_data(country)
    now = _now()
    items = []
    for r in raw:
        currency = "USD"
        suffix = r.get("suffix") or ""
        if suffix and " " in str(suffix):
            parts = str(suffix).strip().split()
            if parts:
                currency = parts[0]
        items.append({
            "symbol": r.get("label", ""),
            "name": r.get("label"),
            "price": r.get("value", 0),
            "change_24h": r.get("change"),
            "currency": currency,
            "refreshed_at": now,
        })
    return MarketsTickerResponse(items=items, last_refreshed_at=now)


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
