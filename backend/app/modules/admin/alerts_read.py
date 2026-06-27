"""Operational read queries for admin alert endpoints (service-data + analytic)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.app_tables import Alert, AlertEvent, ServiceAlert


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def _service_alert_item(row: ServiceAlert) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "alert_class": row.alert_class,
        "module": row.module,
        "submodule": row.submodule,
        "severity": row.severity,
        "anomaly_type": row.anomaly_type,
        "message": row.message,
        "context": row.context,
        "triggered_at": _iso(row.triggered_at),
        "resolved_at": _iso(row.resolved_at),
    }


def _analytic_alert_item(event: AlertEvent, alert: Alert) -> dict[str, Any]:
    return {
        "id": event.id,
        "alert_class": event.alert_class,
        "alert_id": str(event.alert_id),
        "alert_type": alert.alert_type,
        "user_id": str(alert.user_id),
        "listing_id": str(event.listing_id) if event.listing_id else None,
        "severity": event.severity,
        "message": event.message,
        "old_value": float(event.old_value) if event.old_value is not None else None,
        "new_value": float(event.new_value) if event.new_value is not None else None,
        "change_pct": float(event.change_pct) if event.change_pct is not None else None,
        "triggered_at": _iso(event.triggered_at),
        "read_at": _iso(event.read_at),
    }


async def list_service_alerts(
    db: AsyncSession,
    *,
    module: str | None = None,
    submodule: str | None = None,
    severity: str | None = None,
    resolved: Literal["open", "resolved", "all"] = "all",
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    """Paginated service_alerts list for admin panel."""
    filters = []
    if module:
        filters.append(ServiceAlert.module == module)
    if submodule:
        filters.append(ServiceAlert.submodule == submodule)
    if severity:
        filters.append(ServiceAlert.severity == severity)
    if resolved == "open":
        filters.append(ServiceAlert.resolved_at.is_(None))
    elif resolved == "resolved":
        filters.append(ServiceAlert.resolved_at.is_not(None))

    count_stmt = select(func.count()).select_from(ServiceAlert)
    if filters:
        count_stmt = count_stmt.where(*filters)
    total = int((await db.scalar(count_stmt)) or 0)

    stmt = select(ServiceAlert).order_by(ServiceAlert.triggered_at.desc())
    if filters:
        stmt = stmt.where(*filters)
    stmt = stmt.limit(limit).offset(offset)
    rows = (await db.execute(stmt)).scalars().all()

    return {
        "items": [_service_alert_item(row) for row in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


async def list_analytic_alerts(
    db: AsyncSession,
    *,
    alert_type: str | None = None,
    severity: str | None = None,
    user_id: UUID | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    """Paginated alert_events joined to alerts for admin panel."""
    filters = []
    if alert_type:
        filters.append(Alert.alert_type == alert_type)
    if severity:
        filters.append(AlertEvent.severity == severity)
    if user_id is not None:
        filters.append(Alert.user_id == user_id)

    count_stmt = (
        select(func.count())
        .select_from(AlertEvent)
        .join(Alert, AlertEvent.alert_id == Alert.id)
    )
    if filters:
        count_stmt = count_stmt.where(*filters)
    total = int((await db.scalar(count_stmt)) or 0)

    stmt = (
        select(AlertEvent, Alert)
        .join(Alert, AlertEvent.alert_id == Alert.id)
        .order_by(AlertEvent.triggered_at.desc())
    )
    if filters:
        stmt = stmt.where(*filters)
    stmt = stmt.limit(limit).offset(offset)
    rows = (await db.execute(stmt)).all()

    return {
        "items": [_analytic_alert_item(event, alert) for event, alert in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }
