"""META door sync bridge — operational metadata writes via gate + persist."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from app.database import sync_session_factory
from app.modules.data_firewall.firewall import evaluate_market
from app.modules.persist.writer import PersistContext, write_sync


def _serialize_meta_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    return value


def build_scrape_job_fields(*, id: UUID | None = None, **columns: Any) -> dict[str, Any]:
    """Assemble scrape_jobs columns for the META gate (include id for update/delete)."""
    fields: dict[str, Any] = {}
    if id is not None:
        fields["id"] = str(id)
    for key, value in columns.items():
        fields[key] = _serialize_meta_value(value)
    return fields


def build_dim_marketplace_fields(*, id: UUID | None = None, **columns: Any) -> dict[str, Any]:
    """Assemble dim_marketplace columns for the META gate (include id for update/delete)."""
    fields: dict[str, Any] = {}
    if id is not None:
        fields["id"] = str(id)
    for key, value in columns.items():
        fields[key] = _serialize_meta_value(value)
    return fields


def build_scrape_job_failed_fields(
    *,
    id: UUID,
    started_at: datetime | None,
    completed_at: datetime,
) -> dict[str, Any]:
    """Assemble scrape_jobs failed-terminal columns for the META gate."""
    reference = started_at if started_at is not None else completed_at
    duration_ms = int((completed_at - reference).total_seconds() * 1000)
    return build_scrape_job_fields(
        id=id,
        status="failed",
        completed_at=completed_at,
        duration_ms=duration_ms,
    )


@dataclass(frozen=True)
class MetaWriteResult:
    """Outcome of one META door write (one commit per call)."""

    ok: bool
    rows_affected: int | None = None
    no_target: bool = False

    def __bool__(self) -> bool:
        return self.ok


def write_meta_sync(
    *,
    table: str,
    operation: str,
    fields: dict[str, Any],
    reject_source: str,
) -> MetaWriteResult:
    """Open a sync session, run gate + persist, commit once, close."""
    db = sync_session_factory()
    try:
        outcome = evaluate_market(
            fields,
            table=table,
            operation=operation,
            db=db,
            reject_source=reject_source,
        )
        if not outcome.passed or outcome.signed_record is None:
            db.rollback()
            return MetaWriteResult(ok=False)
        ctx = PersistContext(source=reject_source)
        result = write_sync(db, outcome.signed_record, ctx=ctx)
        if not result.ok:
            db.rollback()
            return MetaWriteResult(ok=False)
        db.commit()
        return MetaWriteResult(
            ok=True,
            rows_affected=result.rows_affected,
            no_target=result.no_target,
        )
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


async def write_meta_async(
    *,
    table: str,
    operation: str,
    fields: dict[str, Any],
    reject_source: str,
) -> MetaWriteResult:
    """Cross the sync bridge from async producers (no ORM object on the write path)."""
    return await asyncio.to_thread(
        write_meta_sync,
        table=table,
        operation=operation,
        fields=fields,
        reject_source=reject_source,
    )
