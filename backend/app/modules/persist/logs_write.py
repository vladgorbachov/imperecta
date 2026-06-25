"""LOGS door sync bridge — append-only audit writes via gate + batch persist."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.database import sync_session_factory
from app.modules.data_firewall.firewall import LogsOutcome, evaluate_logs
from app.modules.persist.writer import PersistContext, write_batch_sync


def _serialize_log_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    return value


def build_scrape_log_fields(
    *,
    listing_id: UUID,
    marketplace_id: UUID,
    status: str,
    url: str,
    scrape_job_id: UUID | None = None,
    price_found: float | None = None,
    duration_ms: int | None = None,
    response_code: int | None = None,
    proxy_used: str | None = None,
    scraper_type: str | None = None,
    error_message: str | None = None,
    error_category: str | None = None,
    retry_count: int = 0,
) -> dict[str, Any]:
    """Assemble scrape_logs columns for the LOGS gate."""
    fields: dict[str, Any] = {
        "listing_id": str(listing_id),
        "marketplace_id": str(marketplace_id),
        "status": status,
        "url": url,
        "retry_count": retry_count,
    }
    if scrape_job_id is not None:
        fields["scrape_job_id"] = str(scrape_job_id)
    if price_found is not None:
        fields["price_found"] = price_found
    if duration_ms is not None:
        fields["duration_ms"] = duration_ms
    if response_code is not None:
        fields["response_code"] = response_code
    if proxy_used is not None:
        fields["proxy_used"] = proxy_used
    if scraper_type is not None:
        fields["scraper_type"] = scraper_type
    if error_message is not None:
        fields["error_message"] = error_message
    if error_category is not None:
        fields["error_category"] = error_category
    return fields


def build_api_log_fields(
    *,
    service: str,
    status: str,
    endpoint: str | None = None,
    method: str = "GET",
    status_code: int | None = None,
    duration_ms: int | None = None,
    tokens_used: int | None = None,
    request_size_bytes: int | None = None,
    response_size_bytes: int | None = None,
    error_message: str | None = None,
    user_id: UUID | None = None,
) -> dict[str, Any]:
    """Assemble api_logs columns for the LOGS gate."""
    fields: dict[str, Any] = {
        "service": service,
        "method": method,
        "status": status,
    }
    if endpoint is not None:
        fields["endpoint"] = endpoint
    if status_code is not None:
        fields["status_code"] = status_code
    if duration_ms is not None:
        fields["duration_ms"] = duration_ms
    if tokens_used is not None:
        fields["tokens_used"] = tokens_used
    if request_size_bytes is not None:
        fields["request_size_bytes"] = request_size_bytes
    if response_size_bytes is not None:
        fields["response_size_bytes"] = response_size_bytes
    if error_message is not None:
        fields["error_message"] = error_message
    if user_id is not None:
        fields["user_id"] = str(user_id)
    return fields


@dataclass(frozen=True)
class LogsWriteResult:
    """Outcome of one LOGS door batch write."""

    ok: bool
    inserted_count: int = 0
    rejected_count: int = 0

    def __bool__(self) -> bool:
        return self.ok


def persist_logs_batch(
    db: Session,
    *,
    table: str,
    rows: list[dict[str, Any]],
    reject_source: str,
    commit: bool = True,
) -> LogsWriteResult:
    """Run LOGS gate + batch persist on an existing sync session."""
    outcome = evaluate_logs(rows, table=table, db=db, reject_source=reject_source)
    if outcome.signed_batch is None:
        if commit and outcome.rejected_count:
            db.commit()
        return LogsWriteResult(
            ok=False,
            inserted_count=0,
            rejected_count=outcome.rejected_count,
        )

    result = write_batch_sync(
        db,
        outcome.signed_batch,
        ctx=PersistContext(source=reject_source),
    )
    if not result.ok:
        db.rollback()
        return LogsWriteResult(
            ok=False,
            inserted_count=0,
            rejected_count=outcome.rejected_count + outcome.inserted_count,
        )
    if commit:
        db.commit()
    return LogsWriteResult(
        ok=True,
        inserted_count=outcome.inserted_count,
        rejected_count=outcome.rejected_count,
    )


def write_logs_sync(
    *,
    table: str,
    rows: list[dict[str, Any]],
    reject_source: str,
) -> LogsWriteResult:
    """Open a sync session, run LOGS gate + batch persist, commit once, close."""
    db = sync_session_factory()
    try:
        return persist_logs_batch(
            db,
            table=table,
            rows=rows,
            reject_source=reject_source,
            commit=True,
        )
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


async def write_logs_async(
    *,
    table: str,
    rows: list[dict[str, Any]],
    reject_source: str,
) -> LogsWriteResult:
    """Cross the sync bridge from async producers (plain field dicts only)."""
    return await asyncio.to_thread(
        write_logs_sync,
        table=table,
        rows=rows,
        reject_source=reject_source,
    )
