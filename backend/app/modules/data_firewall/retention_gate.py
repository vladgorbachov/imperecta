"""COMMANDS/maintenance gate for service-data retention deletes."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.modules.data_firewall.firewall import FirewallOutcome, REJECT_SIGNING_UNAVAILABLE
from app.modules.data_firewall.reject_store import write_reject_data_isolated
from app.modules.data_firewall.signing import SignedRecord, sign
from app.modules.persist.retention_config import RETENTION_TABLES

REJECT_RETENTION_TABLE_NOT_WHITELISTED = "retention_table_not_whitelisted"
REJECT_RETENTION_CUTOFF_COLUMN_MISMATCH = "retention_cutoff_column_mismatch"
REJECT_RETENTION_INVALID_FIELDS = "retention_invalid_fields"
REJECT_RETENTION_INVALID_CUTOFF = "retention_invalid_cutoff"


def _reject_outcome(
    *,
    reject_reason: str,
    failed_rules: list[str],
    notes: dict[str, Any] | None = None,
) -> FirewallOutcome:
    return FirewallOutcome(
        passed=False,
        reject_reason=reject_reason,
        failed_rules=failed_rules,
        forced_log_status=None,
        page_role_verdict=None,
        notes=notes or {},
        signed_record=None,
    )


def _isolated_reject(
    *,
    db: Any,
    reject_source: str,
    table: str,
    reject_reason: str,
    failed_rules: list[str],
    fields: dict[str, Any],
) -> None:
    write_reject_data_isolated(
        source=reject_source,
        table_target=table,
        reject_reason=reject_reason,
        failed_rules=failed_rules,
        raw_payload=fields,
        rejected_by="data_firewall",
        signature_present=False,
        operation="retention_delete",
    )


def authorize_retention_delete(
    *,
    table: str,
    fields: dict[str, Any],
    db: Any | None = None,
    reject_source: str = "maintenance_retention",
) -> FirewallOutcome:
    """Authorize a whitelisted retention bulk DELETE (cutoff predicate only)."""
    config = RETENTION_TABLES.get(table)
    if config is None:
        failed_rules = [REJECT_RETENTION_TABLE_NOT_WHITELISTED]
        if db is not None:
            _isolated_reject(
                db=db,
                reject_source=reject_source,
                table=table,
                reject_reason=REJECT_RETENTION_TABLE_NOT_WHITELISTED,
                failed_rules=failed_rules,
                fields=fields,
            )
        return _reject_outcome(
            reject_reason=REJECT_RETENTION_TABLE_NOT_WHITELISTED,
            failed_rules=failed_rules,
            notes={"table": table},
        )

    expected_column = config.cutoff_column
    if set(fields.keys()) != {"cutoff_column", "cutoff"}:
        failed_rules = [REJECT_RETENTION_INVALID_FIELDS]
        if db is not None:
            _isolated_reject(
                db=db,
                reject_source=reject_source,
                table=table,
                reject_reason=REJECT_RETENTION_INVALID_FIELDS,
                failed_rules=failed_rules,
                fields=fields,
            )
        return _reject_outcome(
            reject_reason=REJECT_RETENTION_INVALID_FIELDS,
            failed_rules=failed_rules,
        )

    if fields["cutoff_column"] != expected_column:
        failed_rules = [REJECT_RETENTION_CUTOFF_COLUMN_MISMATCH]
        if db is not None:
            _isolated_reject(
                db=db,
                reject_source=reject_source,
                table=table,
                reject_reason=REJECT_RETENTION_CUTOFF_COLUMN_MISMATCH,
                failed_rules=failed_rules,
                fields=fields,
            )
        return _reject_outcome(
            reject_reason=REJECT_RETENTION_CUTOFF_COLUMN_MISMATCH,
            failed_rules=failed_rules,
        )

    try:
        datetime.fromisoformat(str(fields["cutoff"]))
    except (TypeError, ValueError):
        failed_rules = [REJECT_RETENTION_INVALID_CUTOFF]
        if db is not None:
            _isolated_reject(
                db=db,
                reject_source=reject_source,
                table=table,
                reject_reason=REJECT_RETENTION_INVALID_CUTOFF,
                failed_rules=failed_rules,
                fields=fields,
            )
        return _reject_outcome(
            reject_reason=REJECT_RETENTION_INVALID_CUTOFF,
            failed_rules=failed_rules,
        )

    locator: dict[str, Any] = {}
    signature = sign(
        table=table,
        operation="retention_delete",
        fields=fields,
        locator=locator,
    )
    if signature is None:
        failed_rules = [REJECT_SIGNING_UNAVAILABLE]
        if db is not None:
            _isolated_reject(
                db=db,
                reject_source=reject_source,
                table=table,
                reject_reason=REJECT_SIGNING_UNAVAILABLE,
                failed_rules=failed_rules,
                fields=fields,
            )
        return _reject_outcome(
            reject_reason=REJECT_SIGNING_UNAVAILABLE,
            failed_rules=failed_rules,
        )

    return FirewallOutcome(
        passed=True,
        reject_reason=None,
        failed_rules=[],
        forced_log_status=None,
        page_role_verdict=None,
        notes={"table": table, "cutoff_column": expected_column},
        signed_record=SignedRecord(
            table=table,
            operation="retention_delete",
            locator=locator,
            fields=fields,
            signature=signature,
        ),
    )
