"""User price-alert rules + events feed (P3). Auth-scoped; writes via gate."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

from app.common.deps import CurrentUser, DbSession
from app.modules.alerts.schemas import (
    AlertEventsResponse,
    AlertRule,
    AlertRuleCreate,
    AlertRulesResponse,
    AlertRuleUpdate,
)
from app.modules.alerts.service import AlertRulesService

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("", response_model=AlertRulesResponse)
async def list_alert_rules(current_user: CurrentUser, db: DbSession) -> AlertRulesResponse:
    items, total = await AlertRulesService(db).list_rules(current_user.id)
    return AlertRulesResponse(items=items, total=total)


@router.post("", response_model=AlertRule, status_code=201)
async def create_alert_rule(
    body: AlertRuleCreate,
    current_user: CurrentUser,
    db: DbSession,
) -> AlertRule:
    created = await AlertRulesService(db).create_rule(
        current_user.id, body.model_dump()
    )
    if created is None:
        raise HTTPException(status_code=422, detail="Alert rule rejected")
    return AlertRule(**created)


@router.get("/events", response_model=AlertEventsResponse)
async def list_alert_events(
    current_user: CurrentUser,
    db: DbSession,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> AlertEventsResponse:
    items, total = await AlertRulesService(db).list_events(
        current_user.id, limit=limit, offset=offset
    )
    return AlertEventsResponse(items=items, total=total, limit=limit, offset=offset)


@router.patch("/{rule_id}", response_model=AlertRule)
async def update_alert_rule(
    rule_id: UUID,
    body: AlertRuleUpdate,
    current_user: CurrentUser,
    db: DbSession,
) -> AlertRule:
    updated = await AlertRulesService(db).update_rule(
        current_user.id, rule_id, body.model_dump(exclude_unset=True)
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="Alert rule not found")
    return AlertRule(**updated)


@router.delete("/{rule_id}", status_code=204)
async def delete_alert_rule(
    rule_id: UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> None:
    deleted = await AlertRulesService(db).delete_rule(current_user.id, rule_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Alert rule not found")
