"""ALERTS gate wrapper — build fields, authorize, persist (chat_write pattern)."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from app.database import sync_session_factory
from app.modules.data_firewall.alert_door import authorize_alert_write
from app.modules.persist.writer import PersistContext, write_sync


def _serialize_alert_value(value: Any) -> Any:
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


def build_alert_rule_fields(*, id: UUID | None = None, **columns: Any) -> dict[str, Any]:
    """Locator + provided alerts columns, serialized for signing."""
    fields: dict[str, Any] = {"id": str(id) if id is not None else str(uuid4())}
    for key, value in columns.items():
        fields[key] = _serialize_alert_value(value)
    return fields


def build_alert_event_fields(**columns: Any) -> dict[str, Any]:
    """alert_events columns serialized for signing (append-only: no locator id)."""
    return {
        key: _serialize_alert_value(value)
        for key, value in columns.items()
        if value is not None
    }


@dataclass(frozen=True)
class AlertWriteResult:
    ok: bool
    rows_affected: int | None = None
    no_target: bool = False

    def __bool__(self) -> bool:
        return self.ok


def write_alert_sync(
    *,
    kind: str,
    fields: dict[str, Any],
    reject_source: str,
) -> AlertWriteResult:
    """Open a sync session, run ALERT door + persist, commit once, close."""
    db = sync_session_factory()
    try:
        outcome = authorize_alert_write(
            fields,
            kind=kind,
            reject_source=reject_source,
        )
        if not outcome.passed or outcome.signed_record is None:
            db.rollback()
            return AlertWriteResult(ok=False)
        result = write_sync(
            db,
            outcome.signed_record,
            ctx=PersistContext(source=reject_source),
        )
        if not result.ok:
            db.rollback()
            return AlertWriteResult(ok=False)
        db.commit()
        return AlertWriteResult(
            ok=True,
            rows_affected=result.rows_affected,
            no_target=result.no_target,
        )
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


async def write_alert_async(
    *,
    kind: str,
    fields: dict[str, Any],
    reject_source: str,
) -> AlertWriteResult:
    """Cross the sync bridge from async producers (no ORM mutation on the write path)."""
    return await asyncio.to_thread(
        write_alert_sync,
        kind=kind,
        fields=fields,
        reject_source=reject_source,
    )
