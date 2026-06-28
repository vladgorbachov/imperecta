"""Service-data retention — gate-routed bulk deletes by cutoff column."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import structlog

from app.database import sync_session_factory
from app.modules.data_firewall.retention_gate import authorize_retention_delete
from app.modules.persist.maintenance_audit import record_maintenance_audit
from app.modules.persist.service_alerts_write import (
    build_service_alert_fields,
    write_service_alert_sync,
)
from app.modules.persist.retention_config import RETENTION_TABLES, RetentionTableConfig
from app.modules.persist.writer import PersistContext, PersistResult, write_sync

slog = structlog.get_logger(__name__)


class RetentionTableNotWhitelistedError(ValueError):
    """Raised when retention is requested for a non-whitelisted table."""


def assert_retention_table_whitelisted(table: str) -> str:
    """Return the cutoff column for a whitelisted table or raise."""
    config = RETENTION_TABLES.get(table)
    if config is None:
        raise RetentionTableNotWhitelistedError(
            f"table not in retention whitelist: {table}",
        )
    return config.cutoff_column


def retention_config_for_table(table: str) -> RetentionTableConfig:
    """Return cutoff column and window for a whitelisted table or raise."""
    config = RETENTION_TABLES.get(table)
    if config is None:
        raise RetentionTableNotWhitelistedError(
            f"table not in retention whitelist: {table}",
        )
    return config


def retention_cutoff(*, table: str, now: datetime | None = None) -> datetime:
    """Compute the exclusive upper bound for rows to delete (older than window)."""
    config = retention_config_for_table(table)
    anchor = now or datetime.now(timezone.utc)
    return anchor - timedelta(days=config.window_days)


def _emit_retention_failure_alert(
    *,
    table: str,
    cutoff_column: str,
    cutoff: datetime,
    reject_reason: str | None,
    failed_rules: list[str] | None,
) -> None:
    """Fail-open service alert when retention DELETE is rejected."""
    try:
        fields = build_service_alert_fields(
            module="maintenance",
            submodule="retention",
            severity="error",
            anomaly_type="retention_delete_rejected",
            message=f"Retention delete rejected table={table}",
            context={
                "table": table,
                "cutoff_column": cutoff_column,
                "cutoff": cutoff.isoformat(),
                "reject_reason": reject_reason,
                "failed_rules": failed_rules or [],
            },
        )
        write_service_alert_sync(
            fields=fields,
            reject_source="maintenance_retention",
        )
    except Exception as exc:
        slog.warning(
            "retention_failure_alert_emit_failed",
            table=table,
            exc_type=type(exc).__name__,
        )


def retention_delete_table(
    table: str,
    *,
    now: datetime | None = None,
) -> PersistResult:
    """Delete rows older than the table window for one whitelisted table via the gate."""
    config = retention_config_for_table(table)
    cutoff_column = config.cutoff_column
    cutoff = retention_cutoff(table=table, now=now)
    fields = {
        "cutoff_column": cutoff_column,
        "cutoff": cutoff.isoformat(),
    }

    with sync_session_factory() as db:
        outcome = authorize_retention_delete(
            table=table,
            fields=fields,
            db=db,
            reject_source="maintenance_retention",
        )
        if not outcome.passed or outcome.signed_record is None:
            _emit_retention_failure_alert(
                table=table,
                cutoff_column=cutoff_column,
                cutoff=cutoff,
                reject_reason=outcome.reject_reason,
                failed_rules=outcome.failed_rules,
            )
            slog.error(
                "retention_delete_rejected",
                table=table,
                cutoff_column=cutoff_column,
                cutoff=cutoff.isoformat(),
                reject_reason=outcome.reject_reason,
                failed_rules=outcome.failed_rules,
            )
            return PersistResult(ok=False)

        result = write_sync(
            db,
            outcome.signed_record,
            ctx=PersistContext(source="maintenance_retention"),
        )
        if not result.ok:
            _emit_retention_failure_alert(
                table=table,
                cutoff_column=cutoff_column,
                cutoff=cutoff,
                reject_reason="persist_rejected",
                failed_rules=None,
            )
            slog.error(
                "retention_delete_persist_failed",
                table=table,
                cutoff_column=cutoff_column,
                cutoff=cutoff.isoformat(),
            )
            db.rollback()
            return result

        db.commit()
        return result


def run_retention_pass(*, now: datetime | None = None) -> dict[str, int]:
    """Run retention for every whitelisted service-data table."""
    deleted_by_table: dict[str, int] = {}
    for table in RETENTION_TABLES:
        config = RETENTION_TABLES[table]
        result = retention_delete_table(table, now=now)
        rows = int(result.rows_affected or 0)
        deleted_by_table[table] = rows
        record_maintenance_audit(
            op="RETENTION DELETE",
            target=table,
            status="success" if result.ok else "error",
            detail=(
                f"rows_deleted={rows} cutoff_column={config.cutoff_column} "
                f"retention_days={config.window_days}"
            ),
        )
        if result.ok:
            slog.info(
                "retention_delete_ok",
                table=table,
                rows_deleted=rows,
                retention_days=config.window_days,
            )
    return deleted_by_table
