"""Scrape UPDATE gate — per-kind column allowlist + is_active semantic."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.modules.data_firewall.contracts import TABLE_LOCATORS, extract_locator
from app.modules.data_firewall.firewall import (
    FirewallOutcome,
    REJECT_SIGNING_UNAVAILABLE,
    _sign_fields,
)
from app.modules.data_firewall.reject_store import write_reject_data_isolated

REJECT_UNKNOWN_UPDATE_KIND = "unknown_update_kind"
REJECT_COLUMN_NOT_ALLOWED = "column_not_allowed"
REJECT_MISSING_LOCATOR = "missing_locator"
REJECT_REACTIVATION_FORBIDDEN = "reactivation_forbidden"
REJECT_NOTHING_TO_UPDATE = "nothing_to_update"
REJECT_UNKNOWN_DELETE_TABLE = "unknown_delete_table"
REJECT_UNEXPECTED_DELETE_FIELD = "unexpected_delete_field"

SCRAPE_UPDATE_ALLOWLIST: dict[str, dict[str, frozenset[str]]] = {
    "fact_listing": {
        "listing_scrape_start_reset": frozenset({"consecutive_errors", "last_error"}),
        "listing_success_streak_reset": frozenset({"failure_streak"}),
        "listing_housekeeping_failure": frozenset(
            {"consecutive_errors", "last_error", "failure_streak"},
        ),
        "listing_deactivate": frozenset({"is_active"}),
        "listing_checked": frozenset({"last_checked_at"}),
        "listing_denorm_success": frozenset(
            {"last_price", "last_currency_code", "last_price_changed_at", "last_price_eur"},
        ),
        "listing_denorm_no_change": frozenset(
            {"last_checked_at", "last_price", "last_currency_code", "last_price_eur"},
        ),
    },
    "dim_product": {
        "product_enrich": frozenset({"name", "name_normalized", "image_url"}),
    },
}

SCRAPE_DELETE_TABLES: frozenset[str] = frozenset({"fact_listing", "dim_product"})


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
    operation: str,
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
        operation=operation,
    )


def authorize_scrape_update(
    *,
    table: str,
    kind: str,
    fields: dict[str, Any],
    db: Any | None = None,
    reject_source: str = "scrape_update",
) -> FirewallOutcome:
    """Authorize a scrape-owned UPDATE delta: allowlist + is_active semantic, then sign."""
    table_kinds = SCRAPE_UPDATE_ALLOWLIST.get(table)
    if table_kinds is None or kind not in table_kinds:
        failed_rules = ["unknown_update_kind"]
        if db is not None:
            _isolated_reject(
                db=db,
                reject_source=reject_source,
                table=table,
                operation="update",
                reject_reason=REJECT_UNKNOWN_UPDATE_KIND,
                failed_rules=failed_rules,
                fields=fields,
            )
        return _reject_outcome(
            reject_reason=REJECT_UNKNOWN_UPDATE_KIND,
            failed_rules=failed_rules,
            notes={"table": table, "kind": kind},
        )

    allowed = table_kinds[kind]
    locator_keys = TABLE_LOCATORS.get(table)
    if not locator_keys:
        failed_rules = ["missing_locator_contract"]
        if db is not None:
            _isolated_reject(
                db=db,
                reject_source=reject_source,
                table=table,
                operation="update",
                reject_reason=REJECT_MISSING_LOCATOR,
                failed_rules=failed_rules,
                fields=fields,
            )
        return _reject_outcome(
            reject_reason=REJECT_MISSING_LOCATOR,
            failed_rules=failed_rules,
        )

    missing_locator = [key for key in locator_keys if key not in fields]
    if missing_locator:
        failed_rules = [REJECT_MISSING_LOCATOR]
        if db is not None:
            _isolated_reject(
                db=db,
                reject_source=reject_source,
                table=table,
                operation="update",
                reject_reason=REJECT_MISSING_LOCATOR,
                failed_rules=failed_rules,
                fields=fields,
            )
        return _reject_outcome(
            reject_reason=REJECT_MISSING_LOCATOR,
            failed_rules=failed_rules,
            notes={"missing": missing_locator},
        )

    locator_set = set(locator_keys)
    changed = {key for key in fields if key not in locator_set}
    if not changed:
        failed_rules = [REJECT_NOTHING_TO_UPDATE]
        if db is not None:
            _isolated_reject(
                db=db,
                reject_source=reject_source,
                table=table,
                operation="update",
                reject_reason=REJECT_NOTHING_TO_UPDATE,
                failed_rules=failed_rules,
                fields=fields,
            )
        return _reject_outcome(
            reject_reason=REJECT_NOTHING_TO_UPDATE,
            failed_rules=failed_rules,
        )

    disallowed = sorted(changed - allowed)
    if disallowed:
        failed_rules = [f"{REJECT_COLUMN_NOT_ALLOWED}:{col}" for col in disallowed]
        reject_reason = failed_rules[0]
        if db is not None:
            _isolated_reject(
                db=db,
                reject_source=reject_source,
                table=table,
                operation="update",
                reject_reason=reject_reason,
                failed_rules=failed_rules,
                fields=fields,
            )
        return _reject_outcome(
            reject_reason=reject_reason,
            failed_rules=failed_rules,
            notes={"kind": kind},
        )

    if fields.get("is_active") is True:
        failed_rules = [REJECT_REACTIVATION_FORBIDDEN]
        if db is not None:
            _isolated_reject(
                db=db,
                reject_source=reject_source,
                table=table,
                operation="update",
                reject_reason=REJECT_REACTIVATION_FORBIDDEN,
                failed_rules=failed_rules,
                fields=fields,
            )
        return _reject_outcome(
            reject_reason=REJECT_REACTIVATION_FORBIDDEN,
            failed_rules=failed_rules,
        )

    signed_record = _sign_fields(table, "update", fields)
    if signed_record is None:
        failed_rules = ["signing_secret_missing"]
        if db is not None:
            _isolated_reject(
                db=db,
                reject_source=reject_source,
                table=table,
                operation="update",
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
        notes={"table": table, "kind": kind},
        signed_record=signed_record,
    )


def authorize_scrape_delete(
    *,
    table: str,
    fields: dict[str, Any],
    db: Any | None = None,
    reject_source: str = "scraper_prune",
) -> FirewallOutcome:
    """Authorize a scrape-owned DELETE: locator-only payload, then sign."""
    if table not in SCRAPE_DELETE_TABLES:
        failed_rules = [REJECT_UNKNOWN_DELETE_TABLE]
        if db is not None:
            _isolated_reject(
                db=db,
                reject_source=reject_source,
                table=table,
                operation="delete",
                reject_reason=REJECT_UNKNOWN_DELETE_TABLE,
                failed_rules=failed_rules,
                fields=fields,
            )
        return _reject_outcome(
            reject_reason=REJECT_UNKNOWN_DELETE_TABLE,
            failed_rules=failed_rules,
            notes={"table": table},
        )

    locator_keys = TABLE_LOCATORS.get(table)
    if not locator_keys:
        failed_rules = [REJECT_MISSING_LOCATOR]
        if db is not None:
            _isolated_reject(
                db=db,
                reject_source=reject_source,
                table=table,
                operation="delete",
                reject_reason=REJECT_MISSING_LOCATOR,
                failed_rules=failed_rules,
                fields=fields,
            )
        return _reject_outcome(
            reject_reason=REJECT_MISSING_LOCATOR,
            failed_rules=failed_rules,
        )

    try:
        extract_locator(table, fields)
    except ValueError:
        failed_rules = [REJECT_MISSING_LOCATOR]
        if db is not None:
            _isolated_reject(
                db=db,
                reject_source=reject_source,
                table=table,
                operation="delete",
                reject_reason=REJECT_MISSING_LOCATOR,
                failed_rules=failed_rules,
                fields=fields,
            )
        return _reject_outcome(
            reject_reason=REJECT_MISSING_LOCATOR,
            failed_rules=failed_rules,
        )

    locator_set = set(locator_keys)
    extra = sorted(set(fields.keys()) - locator_set)
    if extra:
        failed_rules = [f"{REJECT_UNEXPECTED_DELETE_FIELD}:{col}" for col in extra]
        reject_reason = failed_rules[0]
        if db is not None:
            _isolated_reject(
                db=db,
                reject_source=reject_source,
                table=table,
                operation="delete",
                reject_reason=reject_reason,
                failed_rules=failed_rules,
                fields=fields,
            )
        return _reject_outcome(
            reject_reason=reject_reason,
            failed_rules=failed_rules,
        )

    signed_record = _sign_fields(table, "delete", fields)
    if signed_record is None:
        failed_rules = ["signing_secret_missing"]
        if db is not None:
            _isolated_reject(
                db=db,
                reject_source=reject_source,
                table=table,
                operation="delete",
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
        notes={"table": table},
        signed_record=signed_record,
    )


__all__ = [
    "REJECT_COLUMN_NOT_ALLOWED",
    "REJECT_MISSING_LOCATOR",
    "REJECT_NOTHING_TO_UPDATE",
    "REJECT_REACTIVATION_FORBIDDEN",
    "REJECT_UNEXPECTED_DELETE_FIELD",
    "REJECT_UNKNOWN_DELETE_TABLE",
    "REJECT_UNKNOWN_UPDATE_KIND",
    "SCRAPE_DELETE_TABLES",
    "SCRAPE_UPDATE_ALLOWLIST",
    "authorize_scrape_delete",
    "authorize_scrape_update",
]
