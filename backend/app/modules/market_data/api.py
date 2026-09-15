"""Market data API."""

from datetime import datetime, timezone

from fastapi import APIRouter

from app.common.deps import CurrentSuperuser, CurrentUser, DbSession
from app.modules.market_data.facade import MarketsService
from app.modules.market_data.schemas import (
    MarketsInstrumentsResponse,
    MarketsPreferencesResponse,
    MarketsPreferencesUpdate,
)

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
async def get_available_instruments(
    current_user: CurrentUser,
    db: DbSession,
) -> MarketsInstrumentsResponse:
    service = MarketsService(db, current_user.id)
    data = await service.get_available_instruments()
    return MarketsInstrumentsResponse(**data)


@router.post("/ingest")
async def trigger_ingest(superuser: CurrentSuperuser) -> dict:
    _ = superuser
    from app.workers.market_data_tasks import ingest_market_data

    task = ingest_market_data.delay()
    return {"status": "enqueued", "task_id": task.id}
