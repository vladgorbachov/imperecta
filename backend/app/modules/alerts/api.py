"""Alerts API endpoints (v2 migration stub)."""

from uuid import UUID

from fastapi import APIRouter, Query

from app.common.deps import CurrentUser, DbSession

router = APIRouter(prefix="/alerts", tags=["alerts"])

_MIG = "Endpoint pending migration to v2 schema"


@router.get("/")
async def list_alerts(current_user: CurrentUser, db: DbSession) -> dict:
    _ = current_user, db
    return {"message": _MIG, "items": [], "total": 0}


@router.post("/")
async def create_alert(current_user: CurrentUser, db: DbSession) -> dict:
    _ = current_user, db
    return {"message": _MIG, "items": [], "total": 0}


@router.put("/{id}")
async def update_alert(id: UUID, current_user: CurrentUser, db: DbSession) -> dict:
    _ = id, current_user, db
    return {"message": _MIG, "items": [], "total": 0}


@router.delete("/{id}")
async def delete_alert(id: UUID, current_user: CurrentUser, db: DbSession) -> dict:
    _ = id, current_user, db
    return {"message": _MIG}


@router.get("/events")
async def list_alert_events(current_user: CurrentUser, db: DbSession, limit: int = Query(20, ge=1, le=100)) -> dict:
    _ = current_user, db, limit
    return {"message": _MIG, "items": [], "total": 0}


@router.get("/events/{event_id}/explanation")
async def get_alert_event_explanation(event_id: int, current_user: CurrentUser, db: DbSession) -> dict:
    _ = event_id, current_user, db
    return {"message": _MIG, "items": [], "total": 0}


@router.post("/events/{event_id}/auto-response")
async def post_alert_event_auto_response(event_id: int, current_user: CurrentUser, db: DbSession) -> dict:
    _ = event_id, current_user, db
    return {"message": _MIG, "items": [], "total": 0}
