"""Admin service-alert resolve (P9): gate-routed UPDATE of resolved_at only.

The gate law decision (per docs/FRONTEND_BACKEND_REQUESTS.md P9): the resolve
UPDATE routes through the META door like every other operational-metadata
write — migration 050 widened gate._operation_allowed('service_alerts') to
include 'update'. This module is the ONLY update producer and builds the
field set as strictly {id, resolved_at}, so the carve-out never grows wider
than the one column the feature needs.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.app_tables import ServiceAlert
from app.modules.persist.meta_write import write_meta_async


async def resolve_service_alert(
    db: AsyncSession,
    alert_id: UUID,
) -> ServiceAlert | None:
    """Set resolved_at = now() (idempotent). None when the id is unknown."""
    row = (
        await db.execute(select(ServiceAlert).where(ServiceAlert.id == alert_id))
    ).scalar_one_or_none()
    if row is None:
        return None
    if row.resolved_at is not None:
        return row  # already resolved — no-op success

    resolved_at = datetime.now(timezone.utc)
    fields: dict[str, Any] = {
        "id": str(alert_id),
        "resolved_at": resolved_at.isoformat(),
    }
    result = await write_meta_async(
        table="service_alerts",
        operation="update",
        fields=fields,
        reject_source="admin_service_alert_resolve",
    )
    if not result.ok:
        raise RuntimeError("service_alerts resolve rejected by gate")

    db.expire(row)
    return (
        await db.execute(select(ServiceAlert).where(ServiceAlert.id == alert_id))
    ).scalar_one_or_none()
