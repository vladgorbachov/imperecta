"""Admin read-only alert endpoints (service + analytic classes)."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.common.deps import CurrentSuperuser, DbSession, get_current_superuser
from app.modules.admin.alerts_read import list_analytic_alerts, list_service_alerts

router = APIRouter(
    prefix="/admin",
    tags=["admin-alerts"],
    dependencies=[Depends(get_current_superuser)],
)


@router.get("/service_alerts")
async def get_service_alerts(
    _current_user: CurrentSuperuser,
    db: DbSession,
    module: str | None = Query(None, max_length=64),
    submodule: str | None = Query(None, max_length=64),
    severity: str | None = Query(None, max_length=10),
    resolved: Literal["open", "resolved", "all"] = Query("all"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> dict:
    """Operational service-health alerts (service-data class)."""
    return await list_service_alerts(
        db,
        module=module,
        submodule=submodule,
        severity=severity,
        resolved=resolved,
        limit=limit,
        offset=offset,
    )


@router.get("/analytic_alerts")
async def get_analytic_alerts(
    _current_user: CurrentSuperuser,
    db: DbSession,
    alert_type: str | None = Query(None, max_length=30),
    severity: str | None = Query(None, max_length=10),
    user_id: UUID | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> dict:
    """Client price-alert events (analytic class; thin read over alerts/alert_events)."""
    return await list_analytic_alerts(
        db,
        alert_type=alert_type,
        severity=severity,
        user_id=user_id,
        limit=limit,
        offset=offset,
    )
