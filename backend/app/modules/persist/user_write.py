"""USER door sync bridge — public.users writes via gate + persist."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from app.database import sync_session_factory
from app.modules.data_firewall.user_door import authorize_user_write
from app.modules.persist.writer import PersistContext, write_sync


def _serialize_user_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    return value


def build_user_fields(*, id: UUID | None = None, **columns: Any) -> dict[str, Any]:
    """Assemble public.users columns for the USER gate (include id for update/delete)."""
    fields: dict[str, Any] = {}
    if id is not None:
        fields["id"] = str(id)
    for key, value in columns.items():
        fields[key] = _serialize_user_value(value)
    return fields


@dataclass(frozen=True)
class UserWriteResult:
    """Outcome of one USER door write (one commit per call)."""

    ok: bool
    rows_affected: int | None = None
    no_target: bool = False

    def __bool__(self) -> bool:
        return self.ok


def write_user_sync(
    *,
    operation: str,
    kind: str,
    fields: dict[str, Any],
    reject_source: str,
) -> UserWriteResult:
    """Open a sync session, run USER gate + persist, commit once, close."""
    db = sync_session_factory()
    try:
        outcome = authorize_user_write(
            fields,
            operation=operation,
            kind=kind,
            db=db,
            reject_source=reject_source,
        )
        if not outcome.passed or outcome.signed_record is None:
            db.rollback()
            return UserWriteResult(ok=False)
        ctx = PersistContext(source=reject_source)
        result = write_sync(db, outcome.signed_record, ctx=ctx)
        if not result.ok:
            db.rollback()
            return UserWriteResult(ok=False)
        db.commit()
        return UserWriteResult(
            ok=True,
            rows_affected=result.rows_affected,
            no_target=result.no_target,
        )
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


async def write_user_async(
    *,
    operation: str,
    kind: str,
    fields: dict[str, Any],
    reject_source: str,
) -> UserWriteResult:
    """Cross the sync bridge from async producers (no ORM mutation on the write path)."""
    return await asyncio.to_thread(
        write_user_sync,
        operation=operation,
        kind=kind,
        fields=fields,
        reject_source=reject_source,
    )
