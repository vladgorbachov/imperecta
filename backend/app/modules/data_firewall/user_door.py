"""USER door — per-kind allowlist + privilege semantic invariants + HMAC sign."""

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
from app.modules.data_firewall.user_active_predicate import may_set_active
from app.modules.data_firewall.user_superuser_predicate import may_set_superuser

USER_TABLE = "users"

REJECT_UNKNOWN_USER_KIND = "unknown_user_kind"
REJECT_COLUMN_NOT_ALLOWED = "column_not_allowed"
REJECT_MISSING_LOCATOR = "missing_locator"
REJECT_NOTHING_TO_UPDATE = "nothing_to_update"
REJECT_UNEXPECTED_DELETE_FIELD = "unexpected_delete_field"
REJECT_PRIVILEGE_ESCALATION = "privilege_escalation"
REJECT_PASSWORD_HASH_FORBIDDEN = "password_hash_forbidden"
REJECT_PLAN_FORBIDDEN = "plan_forbidden"
REJECT_IS_ACTIVE_FORBIDDEN = "is_active_forbidden"
REJECT_REACTIVATION_FORBIDDEN = "reactivation_forbidden"

# Per-kind column allowlists (locator ``id`` is always permitted).
USER_INSERT_ALLOWLIST: dict[str, frozenset[str]] = {
    "register": frozenset(
        {
            "email",
            "password_hash",
            "name",
            "company_name",
            "plan",
            "trial_ends_at",
            "language",
        },
    ),
    "admin_create": frozenset(
        {
            "email",
            "password_hash",
            "name",
            "company_name",
            "plan",
            "language",
            "timezone",
            "is_superuser",
            "force_password_change",
        },
    ),
}

USER_UPDATE_ALLOWLIST: dict[str, frozenset[str]] = {
    "login_touch": frozenset({"last_login_at"}),
    "password_change": frozenset({"email", "password_hash", "force_password_change"}),
    "self_update": frozenset(
        {
            "name",
            "company_name",
            "language",
            "timezone",
            "ai_tone",
            "default_currency",
            "avatar_url",
            "preferences",
        },
    ),
    "telegram_link": frozenset({"telegram_chat_id", "telegram_link_code"}),
    "admin_update": frozenset(
        {
            "email",
            "name",
            "company_name",
            "plan",
            "language",
            "timezone",
            "is_active",
            "is_superuser",
        },
    ),
    "admin_password_reset": frozenset({"password_hash", "force_password_change"}),
}

USER_DELETE_KINDS: frozenset[str] = frozenset({"admin_delete"})

_PASSWORD_HASH_KINDS: frozenset[str] = frozenset(
    {"register", "password_change", "admin_create", "admin_password_reset"},
)
_PLAN_KINDS: frozenset[str] = frozenset({"register", "admin_create", "admin_update"})


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
    operation: str,
    reject_reason: str,
    failed_rules: list[str],
    fields: dict[str, Any],
) -> None:
    write_reject_data_isolated(
        source=reject_source,
        table_target=USER_TABLE,
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


def _check_semantic_invariants(
    *,
    kind: str,
    operation: str,
    changed: set[str],
    fields: dict[str, Any],
) -> tuple[str | None, list[str]]:
    """Return (reject_reason, failed_rules) when a privilege invariant is violated."""
    if "is_superuser" in changed and not may_set_superuser(kind=kind, target_fields=fields):
        return REJECT_PRIVILEGE_ESCALATION, [REJECT_PRIVILEGE_ESCALATION]

    if "password_hash" in changed and kind not in _PASSWORD_HASH_KINDS:
        return REJECT_PASSWORD_HASH_FORBIDDEN, [REJECT_PASSWORD_HASH_FORBIDDEN]

    if "plan" in changed and kind not in _PLAN_KINDS:
        return REJECT_PLAN_FORBIDDEN, [REJECT_PLAN_FORBIDDEN]

    if "is_active" in changed and not may_set_active(kind=kind, target_fields=fields):
        if fields.get("is_active") is True:
            return REJECT_REACTIVATION_FORBIDDEN, [REJECT_REACTIVATION_FORBIDDEN]
        return REJECT_IS_ACTIVE_FORBIDDEN, [REJECT_IS_ACTIVE_FORBIDDEN]

    return None, []


def _validate_contract_subset(fields: dict[str, Any]) -> tuple[bool, list[str], str | None]:
    contract = FACT_TABLE_CONTRACTS.get(USER_TABLE)
    if contract is None:
        return False, ["unknown_table"], "unknown_table"
    return _validate_against_contract(fields, contract)


def authorize_user_write(
    fields: dict[str, Any],
    *,
    operation: str,
    kind: str,
    db: Any | None = None,
    reject_source: str = "user_write",
) -> FirewallOutcome:
    """Authorize a public.users write: per-kind allowlist + privilege semantics + sign."""
    table = USER_TABLE
    locator_keys = TABLE_LOCATORS.get(table)
    if not locator_keys:
        return _reject(
            reject_source=reject_source,
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
            operation=operation,
            reject_reason=REJECT_MISSING_LOCATOR,
            failed_rules=[REJECT_MISSING_LOCATOR],
            fields=fields,
            db=db,
            notes={"missing": missing_locator},
        )

    if operation == "insert":
        allowed = USER_INSERT_ALLOWLIST.get(kind)
        if allowed is None:
            return _reject(
                reject_source=reject_source,
                operation=operation,
                reject_reason=REJECT_UNKNOWN_USER_KIND,
                failed_rules=["unknown_user_kind"],
                fields=fields,
                db=db,
                notes={"kind": kind},
            )
        locator_set = set(locator_keys)
        payload_keys = set(fields.keys()) - locator_set
        disallowed = sorted(payload_keys - allowed)
        if disallowed:
            failed_rules = [f"{REJECT_COLUMN_NOT_ALLOWED}:{col}" for col in disallowed]
            return _reject(
                reject_source=reject_source,
                operation=operation,
                reject_reason=failed_rules[0],
                failed_rules=failed_rules,
                fields=fields,
                db=db,
                notes={"kind": kind},
            )
        semantic_reason, semantic_rules = _check_semantic_invariants(
            kind=kind,
            operation=operation,
            changed=payload_keys,
            fields=fields,
        )
        if semantic_reason is not None:
            return _reject(
                reject_source=reject_source,
                operation=operation,
                reject_reason=semantic_reason,
                failed_rules=semantic_rules,
                fields=fields,
                db=db,
            )
        passed, failed_rules, reject_reason = _validate_contract_subset(fields)
        if not passed:
            return _reject(
                reject_source=reject_source,
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

    if operation == "update":
        allowed = USER_UPDATE_ALLOWLIST.get(kind)
        if allowed is None:
            return _reject(
                reject_source=reject_source,
                operation=operation,
                reject_reason=REJECT_UNKNOWN_USER_KIND,
                failed_rules=["unknown_user_kind"],
                fields=fields,
                db=db,
                notes={"kind": kind},
            )
        locator_set = set(locator_keys)
        changed = {key for key in fields if key not in locator_set}
        if not changed:
            return _reject(
                reject_source=reject_source,
                operation=operation,
                reject_reason=REJECT_NOTHING_TO_UPDATE,
                failed_rules=[REJECT_NOTHING_TO_UPDATE],
                fields=fields,
                db=db,
            )
        disallowed = sorted(changed - allowed)
        if disallowed:
            failed_rules = [f"{REJECT_COLUMN_NOT_ALLOWED}:{col}" for col in disallowed]
            return _reject(
                reject_source=reject_source,
                operation=operation,
                reject_reason=failed_rules[0],
                failed_rules=failed_rules,
                fields=fields,
                db=db,
                notes={"kind": kind},
            )
        semantic_reason, semantic_rules = _check_semantic_invariants(
            kind=kind,
            operation=operation,
            changed=changed,
            fields=fields,
        )
        if semantic_reason is not None:
            return _reject(
                reject_source=reject_source,
                operation=operation,
                reject_reason=semantic_reason,
                failed_rules=semantic_rules,
                fields=fields,
                db=db,
            )
        passed, failed_rules, reject_reason = _validate_contract_subset(
            {key: fields[key] for key in changed},
        )
        if not passed:
            return _reject(
                reject_source=reject_source,
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

    if operation == "delete":
        if kind not in USER_DELETE_KINDS:
            return _reject(
                reject_source=reject_source,
                operation=operation,
                reject_reason=REJECT_UNKNOWN_USER_KIND,
                failed_rules=["unknown_user_kind"],
                fields=fields,
                db=db,
                notes={"kind": kind},
            )
        try:
            extract_locator(table, fields)
        except ValueError:
            return _reject(
                reject_source=reject_source,
                operation=operation,
                reject_reason=REJECT_MISSING_LOCATOR,
                failed_rules=[REJECT_MISSING_LOCATOR],
                fields=fields,
                db=db,
            )
        locator_set = set(locator_keys)
        extra = sorted(set(fields.keys()) - locator_set)
        if extra:
            failed_rules = [f"{REJECT_UNEXPECTED_DELETE_FIELD}:{col}" for col in extra]
            return _reject(
                reject_source=reject_source,
                operation=operation,
                reject_reason=failed_rules[0],
                failed_rules=failed_rules,
                fields=fields,
                db=db,
            )
        signed_record = _sign_fields(table, operation, fields)
        if signed_record is None:
            return _reject(
                reject_source=reject_source,
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

    return _reject(
        reject_source=reject_source,
        operation=operation,
        reject_reason="unsupported_operation",
        failed_rules=["unsupported_operation"],
        fields=fields,
        db=db,
    )


__all__ = [
    "REJECT_COLUMN_NOT_ALLOWED",
    "REJECT_IS_ACTIVE_FORBIDDEN",
    "REJECT_MISSING_LOCATOR",
    "REJECT_NOTHING_TO_UPDATE",
    "REJECT_PASSWORD_HASH_FORBIDDEN",
    "REJECT_PLAN_FORBIDDEN",
    "REJECT_PRIVILEGE_ESCALATION",
    "REJECT_REACTIVATION_FORBIDDEN",
    "REJECT_UNEXPECTED_DELETE_FIELD",
    "REJECT_UNKNOWN_USER_KIND",
    "USER_DELETE_KINDS",
    "USER_INSERT_ALLOWLIST",
    "USER_TABLE",
    "USER_UPDATE_ALLOWLIST",
    "authorize_user_write",
    "may_set_active",
    "may_set_superuser",
]
