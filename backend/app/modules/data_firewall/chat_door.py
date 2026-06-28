"""CHAT door — owner-scope invariant + per-kind allowlist + HMAC sign."""

from __future__ import annotations

from typing import Any

from app.modules.data_firewall.contracts import FACT_TABLE_CONTRACTS, TABLE_LOCATORS, extract_locator
from app.modules.data_firewall.firewall import (
    FirewallOutcome,
    REJECT_SIGNING_UNAVAILABLE,
    _sign_fields,
    _validate_against_contract,
)
from app.modules.data_firewall.reject_store import write_reject_data_isolated

SESSIONS_TABLE = "ai_chat_sessions"
MESSAGES_TABLE = "ai_chat_messages"

REJECT_UNKNOWN_CHAT_KIND = "unknown_chat_kind"
REJECT_COLUMN_NOT_ALLOWED = "column_not_allowed"
REJECT_MISSING_LOCATOR = "missing_locator"
REJECT_OWNER_MISSING = "owner_missing"
REJECT_INVALID_MESSAGE_ROLE = "invalid_message_role"
REJECT_UNSUPPORTED_OPERATION = "unsupported_operation"

MESSAGE_APPEND_ROLES: frozenset[str] = frozenset({"user", "assistant"})

CHAT_INSERT_ALLOWLIST: dict[str, dict[str, frozenset[str]]] = {
    SESSIONS_TABLE: {
        "session_create": frozenset(
            {"user_id", "title", "context_type", "context_id"},
        ),
    },
    MESSAGES_TABLE: {
        "message_append": frozenset(
            {
                "session_id",
                "role",
                "content",
                "tokens_used",
                "model_used",
                "duration_ms",
                "tool_calls",
                "user_rating",
            },
        ),
    },
}


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


def _reject(
    *,
    reject_source: str,
    table: str,
    operation: str,
    reject_reason: str,
    failed_rules: list[str],
    fields: dict[str, Any],
    db: Any | None,
    notes: dict[str, Any] | None = None,
) -> FirewallOutcome:
    if db is not None:
        _isolated_reject(
            reject_source=reject_source,
            table=table,
            operation=operation,
            reject_reason=reject_reason,
            failed_rules=failed_rules,
            fields=fields,
        )
    return _reject_outcome(
        reject_reason=reject_reason,
        failed_rules=failed_rules,
        notes=notes,
    )


def _owner_present(*, table: str, fields: dict[str, Any]) -> bool:
    """Owner-scope: sessions require user_id; messages require session_id."""
    if table == SESSIONS_TABLE:
        user_id = fields.get("user_id")
        return user_id is not None and str(user_id).strip() != ""
    if table == MESSAGES_TABLE:
        session_id = fields.get("session_id")
        return session_id is not None and str(session_id).strip() != ""
    return False


def _validate_contract_subset(table: str, fields: dict[str, Any]) -> tuple[bool, list[str], str | None]:
    contract = FACT_TABLE_CONTRACTS.get(table)
    if contract is None:
        return False, ["unknown_table"], "unknown_table"
    return _validate_against_contract(fields, contract)


def authorize_chat_write(
    fields: dict[str, Any],
    *,
    operation: str,
    table: str,
    kind: str,
    db: Any | None = None,
    reject_source: str = "chat_write",
) -> FirewallOutcome:
    """Authorize an ai_chat_* write: owner-scope + allowlist + sign."""
    if operation != "insert":
        return _reject(
            reject_source=reject_source,
            table=table,
            operation=operation,
            reject_reason=REJECT_UNSUPPORTED_OPERATION,
            failed_rules=["unsupported_operation"],
            fields=fields,
            db=db,
        )

    table_kinds = CHAT_INSERT_ALLOWLIST.get(table)
    if table_kinds is None or kind not in table_kinds:
        return _reject(
            reject_source=reject_source,
            table=table,
            operation=operation,
            reject_reason=REJECT_UNKNOWN_CHAT_KIND,
            failed_rules=["unknown_chat_kind"],
            fields=fields,
            db=db,
            notes={"table": table, "kind": kind},
        )

    locator_keys = TABLE_LOCATORS.get(table)
    if not locator_keys:
        return _reject(
            reject_source=reject_source,
            table=table,
            operation=operation,
            reject_reason=REJECT_MISSING_LOCATOR,
            failed_rules=["missing_locator_contract"],
            fields=fields,
            db=db,
        )

    missing_locator = [key for key in locator_keys if key not in fields]
    if missing_locator:
        return _reject(
            reject_source=reject_source,
            table=table,
            operation=operation,
            reject_reason=REJECT_MISSING_LOCATOR,
            failed_rules=[REJECT_MISSING_LOCATOR],
            fields=fields,
            db=db,
            notes={"missing": missing_locator},
        )

    if not _owner_present(table=table, fields=fields):
        return _reject(
            reject_source=reject_source,
            table=table,
            operation=operation,
            reject_reason=REJECT_OWNER_MISSING,
            failed_rules=[REJECT_OWNER_MISSING],
            fields=fields,
            db=db,
        )

    allowed = table_kinds[kind]
    locator_set = set(locator_keys)
    payload_keys = set(fields.keys()) - locator_set
    disallowed = sorted(payload_keys - allowed)
    if disallowed:
        failed_rules = [f"{REJECT_COLUMN_NOT_ALLOWED}:{col}" for col in disallowed]
        return _reject(
            reject_source=reject_source,
            table=table,
            operation=operation,
            reject_reason=failed_rules[0],
            failed_rules=failed_rules,
            fields=fields,
            db=db,
            notes={"kind": kind},
        )

    if table == MESSAGES_TABLE and kind == "message_append":
        role = fields.get("role")
        if role not in MESSAGE_APPEND_ROLES:
            return _reject(
                reject_source=reject_source,
                table=table,
                operation=operation,
                reject_reason=REJECT_INVALID_MESSAGE_ROLE,
                failed_rules=[REJECT_INVALID_MESSAGE_ROLE],
                fields=fields,
                db=db,
            )

    passed, failed_rules, reject_reason = _validate_contract_subset(table, fields)
    if not passed:
        return _reject(
            reject_source=reject_source,
            table=table,
            operation=operation,
            reject_reason=reject_reason or "contract_violation",
            failed_rules=failed_rules,
            fields=fields,
            db=db,
        )

    signed_record = _sign_fields(table, operation, fields)
    if signed_record is None:
        return _reject(
            reject_source=reject_source,
            table=table,
            operation=operation,
            reject_reason=REJECT_SIGNING_UNAVAILABLE,
            failed_rules=["signing_secret_missing"],
            fields=fields,
            db=db,
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


__all__ = [
    "CHAT_INSERT_ALLOWLIST",
    "MESSAGES_TABLE",
    "MESSAGE_APPEND_ROLES",
    "REJECT_COLUMN_NOT_ALLOWED",
    "REJECT_INVALID_MESSAGE_ROLE",
    "REJECT_MISSING_LOCATOR",
    "REJECT_OWNER_MISSING",
    "REJECT_UNKNOWN_CHAT_KIND",
    "SESSIONS_TABLE",
    "authorize_chat_write",
]
