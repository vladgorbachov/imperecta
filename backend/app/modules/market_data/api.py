"""Market data API."""

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query

from app.common.deps import CurrentSuperuser, CurrentUser, DbSession
from app.modules.market_data.schemas import (
    MarketsCommoditiesResponse,
    MarketsCryptoResponse,
    MarketsForexResponse,
    MarketsPreferencesResponse,
    MarketsPreferencesUpdate,
    MarketsRefreshMetadataResponse,
    MarketsRefreshStatusItem,
    MarketsTickerResponse,
)
from app.modules.market_data.service import (
    MarketDataService,
    MarketsService,
    fetch_crypto_prices,
    fetch_forex_rates,
    get_fuel_prices,
    get_ticker_data,
)

router = APIRouter(prefix="/markets", tags=["markets"])

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
]


def _now() -> datetime:
    return datetime.now(timezone.utc)


@router.get("/countries")
async def get_countries(current_user: CurrentUser) -> list[dict]:
    _ = current_user
    meta = [
        {"code": "EUROPE", "name": "Europe", "name_local": "Европа", "flag": "🇪🇺", "region": "meta", "is_region": True},
        {"code": "CIS", "name": "CIS", "name_local": "СНГ", "flag": "🌍", "region": "meta", "is_region": True},
        {"separator": True},
    ]
    return meta + COUNTRIES


@router.get("/preferences", response_model=MarketsPreferencesResponse)
async def get_preferences(current_user: CurrentUser, db: DbSession) -> MarketsPreferencesResponse:
    service = MarketsService(db, current_user.id)
    data = await service.get_preferences()
    return MarketsPreferencesResponse(**data)


@router.put("/preferences", response_model=MarketsPreferencesResponse)
async def update_preferences(
    body: MarketsPreferencesUpdate,
    current_user: CurrentUser,
    db: DbSession,
) -> MarketsPreferencesResponse:
    service = MarketsService(db, current_user.id)
    data = await service.update_preferences(**body.model_dump(exclude_unset=True))
    return MarketsPreferencesResponse(**data)


@router.get("/refresh-metadata", response_model=MarketsRefreshMetadataResponse)
async def get_refresh_metadata(current_user: CurrentUser, db: DbSession) -> MarketsRefreshMetadataResponse:
    service = MarketsService(db, current_user.id)
    raw = await service.get_refresh_metadata()
    items = [
        MarketsRefreshStatusItem(
            refresh_type=row["refresh_type"],
            last_successful_refresh=row.get("last_successful_refresh"),
            last_failed_refresh=row.get("last_failed_refresh"),
            provider_source=row.get("provider_source"),
            country_scope=row.get("country_scope"),
            error_message=row.get("error_message"),
        )
        for row in raw
    ]
    return MarketsRefreshMetadataResponse(items=items)


@router.get("/forex", response_model=MarketsForexResponse)
async def get_forex(current_user: CurrentUser, db: DbSession) -> MarketsForexResponse:
    _ = current_user
    mds = MarketDataService(db)
    db_items, last_at = await mds.build_forex_api_response_async()
    if db_items:
        return MarketsForexResponse(items=db_items, last_refreshed_at=last_at)
    raw = await fetch_forex_rates("EUR")
    if not raw:
        raise HTTPException(503, "Forex data temporarily unavailable")
    now = _now()
    items = [
        {
            "symbol": pair["pair"],
            "bid": pair["rate"],
            "ask": pair["rate"],
            "spread": 0,
            "change_24h": pair.get("change_24h"),
            "refreshed_at": now,
        }
        for pair in raw
    ]
    return MarketsForexResponse(items=items, last_refreshed_at=now)


@router.get("/crypto", response_model=MarketsCryptoResponse)
async def get_crypto(current_user: CurrentUser, db: DbSession) -> MarketsCryptoResponse:
    _ = current_user
    now = _now()
    mds = MarketDataService(db)
    db_items, last_at, _cached = await mds.build_crypto_api_response_async()
    if db_items:
        return MarketsCryptoResponse(
            items=db_items,
            error=None,
            cached=False,
            last_refreshed_at=last_at,
        )
    try:
        raw, from_cache = await fetch_crypto_prices()
        items = [
            {
                "symbol": coin["symbol"],
                "price": coin["price"],
                "change_24h": coin.get("change_24h"),
                "market_cap": coin.get("market_cap"),
                "refreshed_at": now,
            }
            for coin in raw
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
            error="Crypto API unavailable. Retry later.",
            cached=False,
            last_refreshed_at=now,
        )


@router.get("/commodities", response_model=MarketsCommoditiesResponse)
async def get_commodities(current_user: CurrentUser, db: DbSession) -> MarketsCommoditiesResponse:
    """Return commodities from DB. Data refreshed 4x/day by ingest_commodities task."""
    _ = current_user
    service = MarketsService(db, current_user.id)
    raw_items, last_at = await service.get_commodities_from_db()
    items = [
        {
            "symbol": c["symbol"],
            "name": c.get("name"),
            "price": c["price"],
            "change_24h": c.get("change_24h"),
            "unit": c.get("unit"),
            "refreshed_at": c["refreshed_at"],
        }
        for c in raw_items
    ]
    return MarketsCommoditiesResponse(
        items=items,
        error=None,
        cached=False,
        last_refreshed_at=last_at or _now(),
    )


@router.get("/fuel")
async def get_fuel(
    current_user: CurrentUser,
    db: DbSession,
    country: str = Query("UA", description="Country code or EUROPE/CIS"),
) -> dict:
    _ = current_user
    data = await get_fuel_prices(country, db=db)
    if not data:
        raise HTTPException(404, f"No fuel data for country: {country}")
    return data


@router.get("/ticker", response_model=MarketsTickerResponse)
async def get_ticker(
    current_user: CurrentUser,
    db: DbSession,
    country: str = Query("UA", description="Country code for fuel data"),
) -> MarketsTickerResponse:
    _ = current_user
    raw = await get_ticker_data(country, db=db)
    now = _now()
    items = []
    for row in raw:
        currency = "USD"
        suffix = row.get("suffix") or ""
        if suffix and " " in str(suffix):
            parts = str(suffix).strip().split()
            if parts:
                currency = parts[0]
        items.append({
            "symbol": row.get("label", ""),
            "name": row.get("label"),
            "price": row.get("value", 0),
            "change_24h": row.get("change"),
            "currency": currency,
            "refreshed_at": now,
        })
    return MarketsTickerResponse(items=items, last_refreshed_at=now)


@router.post("/ingest")
async def trigger_ingest(superuser: CurrentSuperuser) -> dict:
    _ = superuser
    from app.modules.market_data.tasks import ingest_market_data

    task = ingest_market_data.delay()
    return {"status": "enqueued", "task_id": task.id}
