"""Best-effort maintenance audit marks via LOGS door (api_logs)."""

from __future__ import annotations

import asyncio
from typing import Literal
from uuid import UUID

import structlog

from app.modules.persist.logs_write import build_api_log_fields, write_logs_sync

slog = structlog.get_logger(__name__)

_MAINTENANCE_SERVICE = "maintenance"
_VALID_STATUSES = frozenset({"success", "error", "timeout", "rate_limited"})

_OP_METHOD: dict[str, str] = {
    "REFRESH MV": "REFRESH",
    "CREATE PARTITION": "DDL",
    "RETENTION DELETE": "DELETE",
    "CHECK REPAIR": "ALTER",
    "ALTER": "ALTER",
}


def _method_for_op(op: str) -> str:
    """Map maintenance op label to api_logs.method (max 10 chars)."""
    method = _OP_METHOD.get(op, op[:10].upper())
    if len(method) > 10:
        return method[:10]
    return method


def record_maintenance_audit(
    *,
    op: str,
    target: str,
    status: Literal["success", "error"],
    user_id: UUID | None = None,
    detail: str | None = None,
    duration_ms: int | None = None,
) -> None:
    """Write an api_logs audit mark; swallows failures (never raises)."""
    if status not in _VALID_STATUSES:
        slog.warning("maintenance_audit_invalid_status", op=op, target=target, status=status)
        return

    endpoint = f"{op}:{target}"
    if len(endpoint) > 500:
        endpoint = endpoint[:500]

    try:
        row = build_api_log_fields(
            service=_MAINTENANCE_SERVICE,
            endpoint=endpoint,
            method=_method_for_op(op),
            status=status,
            user_id=user_id,
            error_message=detail,
            duration_ms=duration_ms,
        )
        result = write_logs_sync(
            table="api_logs",
            rows=[row],
            reject_source="maintenance_audit",
        )
        if not result.ok:
            slog.warning(
                "maintenance_audit_rejected",
                op=op,
                target=target,
                status=status,
            )
    except Exception as exc:
        slog.warning(
            "maintenance_audit_failed",
            op=op,
            target=target,
            status=status,
            error=str(exc)[:500],
        )


async def record_maintenance_audit_async(
    *,
    op: str,
    target: str,
    status: Literal["success", "error"],
    user_id: UUID | None = None,
    detail: str | None = None,
    duration_ms: int | None = None,
) -> None:
    """Async bridge for maintenance audit marks (plain dict, no ORM)."""
    await asyncio.to_thread(
        record_maintenance_audit,
        op=op,
        target=target,
        status=status,
        user_id=user_id,
        detail=detail,
        duration_ms=duration_ms,
    )
