"""CHAT door sync bridge — ai_chat_sessions / ai_chat_messages via gate + persist."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import text

from app.database import sync_session_factory
from app.modules.data_firewall.chat_door import MESSAGES_TABLE, authorize_chat_write
from app.modules.persist.writer import PersistContext, write_sync

_CHAT_MESSAGE_ID_SEQUENCE = "ai_chat_messages_id_seq"


def _serialize_chat_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    return value


def build_chat_session_fields(*, id: UUID | None = None, **columns: Any) -> dict[str, Any]:
    """Assemble ai_chat_sessions columns for the CHAT gate."""
    fields: dict[str, Any] = {}
    if id is not None:
        fields["id"] = str(id)
    for key, value in columns.items():
        fields[key] = _serialize_chat_value(value)
    return fields


def build_chat_message_fields(
    *,
    id: int | None = None,
    session_id: UUID,
    role: str,
    content: str,
    **columns: Any,
) -> dict[str, Any]:
    """Assemble ai_chat_messages columns for the CHAT gate."""
    fields: dict[str, Any] = {
        "session_id": str(session_id),
        "role": role,
        "content": content,
    }
    if id is not None:
        fields["id"] = id
    for key, value in columns.items():
        fields[key] = _serialize_chat_value(value)
    return fields


def _allocate_message_id(db: Any) -> int:
    result = db.execute(text(f"SELECT nextval('{_CHAT_MESSAGE_ID_SEQUENCE}')"))
    return int(result.scalar_one())


@dataclass(frozen=True)
class ChatWriteResult:
    """Outcome of one CHAT door write (one commit per call)."""

    ok: bool
    rows_affected: int | None = None
    no_target: bool = False
    allocated_message_id: int | None = None

    def __bool__(self) -> bool:
        return self.ok


def write_chat_sync(
    *,
    table: str,
    operation: str,
    kind: str,
    fields: dict[str, Any],
    reject_source: str,
) -> ChatWriteResult:
    """Open a sync session, run CHAT gate + persist, commit once, close."""
    db = sync_session_factory()
    allocated_message_id: int | None = None
    payload = dict(fields)
    try:
        if table == MESSAGES_TABLE and "id" not in payload:
            allocated_message_id = _allocate_message_id(db)
            payload["id"] = allocated_message_id
        outcome = authorize_chat_write(
            payload,
            operation=operation,
            table=table,
            kind=kind,
            db=db,
            reject_source=reject_source,
        )
        if not outcome.passed or outcome.signed_record is None:
            db.rollback()
            return ChatWriteResult(ok=False)
        ctx = PersistContext(source=reject_source)
        result = write_sync(db, outcome.signed_record, ctx=ctx)
        if not result.ok:
            db.rollback()
            return ChatWriteResult(ok=False)
        db.commit()
        return ChatWriteResult(
            ok=True,
            rows_affected=result.rows_affected,
            no_target=result.no_target,
            allocated_message_id=allocated_message_id,
        )
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


async def write_chat_async(
    *,
    table: str,
    operation: str,
    kind: str,
    fields: dict[str, Any],
    reject_source: str,
) -> ChatWriteResult:
    """Cross the sync bridge from async producers (no ORM mutation on the write path)."""
    return await asyncio.to_thread(
        write_chat_sync,
        table=table,
        operation=operation,
        kind=kind,
        fields=fields,
        reject_source=reject_source,
    )
