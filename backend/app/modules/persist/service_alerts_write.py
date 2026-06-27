"""SERVICE-ALERTS door sync bridge — gate-writable operational alert inserts."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from app.modules.persist.meta_write import MetaWriteResult, write_meta_sync


def build_service_alert_fields(
    *,
    module: str,
    submodule: str,
    severity: str,
    anomaly_type: str,
    message: str,
    id: UUID | None = None,
    alert_class: str = "service",
    context: dict[str, Any] | None = None,
    triggered_at: datetime | None = None,
    resolved_at: datetime | None = None,
) -> dict[str, Any]:
    """Assemble service_alerts columns for the META gate (include id for insert)."""
    row_id = id or uuid4()
    fields: dict[str, Any] = {
        "id": str(row_id),
        "alert_class": alert_class,
        "module": module,
        "submodule": submodule,
        "severity": severity,
        "anomaly_type": anomaly_type,
        "message": message,
    }
    if context is not None:
        fields["context"] = context
    if triggered_at is not None:
        fields["triggered_at"] = triggered_at.isoformat()
    if resolved_at is not None:
        fields["resolved_at"] = resolved_at.isoformat()
    return fields


@dataclass(frozen=True)
class ServiceAlertWriteResult:
    """Outcome of one service_alerts gate write."""

    ok: bool
    rows_affected: int | None = None

    def __bool__(self) -> bool:
        return self.ok


def write_service_alert_sync(
    *,
    fields: dict[str, Any],
    reject_source: str,
) -> ServiceAlertWriteResult:
    """Insert one service alert row through evaluate_market + persist."""
    result = write_meta_sync(
        table="service_alerts",
        operation="insert",
        fields=fields,
        reject_source=reject_source,
    )
    return ServiceAlertWriteResult(ok=result.ok, rows_affected=result.rows_affected)


async def write_service_alert_async(
    *,
    fields: dict[str, Any],
    reject_source: str,
) -> ServiceAlertWriteResult:
    """Cross the sync bridge from async producers."""
    return await asyncio.to_thread(
        write_service_alert_sync,
        fields=fields,
        reject_source=reject_source,
    )
