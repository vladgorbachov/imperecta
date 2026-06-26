"""Market data API."""

from datetime import datetime, timezone

from fastapi import APIRouter

from app.common.deps import CurrentSuperuser, CurrentUser, DbSession
from app.modules.market_data.schemas import (
    MarketsInstrumentsResponse,
    MarketsPreferencesResponse,
    MarketsPreferencesUpdate,
    MarketsTickerResponse,
)
from app.modules.market_data.facade import MarketsService
from app.modules.market_data.ticker import get_ticker_data

router = APIRouter(prefix="/markets", tags=["markets"])
DEFAULT_TICKER_COUNTRY = "DE"


def _now() -> datetime:
    return datetime.now(timezone.utc)


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


@router.get("/instruments", response_model=MarketsInstrumentsResponse)
async def get_available_instruments(current_user: CurrentUser, db: DbSession) -> MarketsInstrumentsResponse:
    service = MarketsService(db, current_user.id)
    data = await service.get_available_instruments()
    return MarketsInstrumentsResponse(**data)


@router.get("/ticker", response_model=MarketsTickerResponse)
async def get_ticker(
    current_user: CurrentUser,
    db: DbSession,
) -> MarketsTickerResponse:
    service = MarketsService(db, current_user.id)
    preferences = await service.get_preferences()
    country_code = DEFAULT_TICKER_COUNTRY
    raw = await get_ticker_data(
        country_code,
        db=db,
        forex_favorites=preferences.get("forex_favorites"),
        crypto_favorites=preferences.get("crypto_favorites"),
        commodity_favorites=preferences.get("commodity_favorites"),
    )
    now = _now()
    items = []
    for row in raw:
        currency: str | None = None
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
    from app.workers.market_data_tasks import ingest_market_data

    task = ingest_market_data.delay()
    return {"status": "enqueued", "task_id": task.id}
