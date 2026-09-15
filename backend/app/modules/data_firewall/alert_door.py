"""USER-DATA door for public.alerts — per-kind allowlist + semantics + sign.

Client price-alert rules are user data: every write is bound to the owning
user_id at signing time (the service passes the authenticated user's id; the
door refuses a payload without it on create). Reads stay operational SELECTs
in the alerts module.
"""

from __future__ import annotations

from typing import Any

from app.modules.data_firewall.chat_door import _validate_contract_subset
from app.modules.data_firewall.firewall import FirewallOutcome, _sign_fields
from app.modules.data_firewall.reject_store import write_reject_data_isolated

ALERTS_TABLE = "alerts"
ALERT_EVENTS_TABLE = "alert_events"

ALERT_TYPES = frozenset({"price_drop", "price_rise", "availability"})
ALERT_CHANNELS = frozenset({"email", "telegram", "webhook"})
EVENT_SEVERITIES = frozenset({"low", "medium", "high", "critical"})

REJECT_UNKNOWN_ALERT_KIND = "unknown_alert_kind"
REJECT_ALERT_FIELD_NOT_ALLOWED = "alert_field_not_allowed"
REJECT_ALERT_SEMANTICS = "alert_semantics"

ALERT_WRITE_ALLOWLIST: dict[str, frozenset[str]] = {
    "rule_create": frozenset(
        {
            "id",
            "user_id",
            "listing_id",
            "product_id",
            "marketplace_id",
            "category_id",
            "country_code",
            "alert_type",
            "threshold_pct",
            "threshold_value",
            "channel",
            "webhook_url",
            "cooldown_minutes",
            "is_active",
            "trigger_count",
            "alert_class",
        }
    ),
    "rule_update": frozenset(
        {
            "id",
            "alert_type",
            "threshold_pct",
            "threshold_value",
            "channel",
            "webhook_url",
            "cooldown_minutes",
            "is_active",
        }
    ),
    "rule_delete": frozenset({"id"}),
    # Server-side kinds (trigger engine) — never reachable from the API layer.
    "rule_trigger": frozenset({"id", "last_triggered_at", "trigger_count"}),
    "event_create": frozenset(
        {
            "alert_id",
            "alert_class",
            "listing_id",
            "fact_price_id",
            "old_value",
            "new_value",
            "change_pct",
            "message",
            "severity",
            "sent_via",
            "delivered_at",
            "triggered_at",
        }
    ),
}

# kind -> (table, operation)
_KIND_TARGETS: dict[str, tuple[str, str]] = {
    "rule_create": (ALERTS_TABLE, "insert"),
    "rule_update": (ALERTS_TABLE, "update"),
    "rule_delete": (ALERTS_TABLE, "delete"),
    "rule_trigger": (ALERTS_TABLE, "update"),
    "event_create": (ALERT_EVENTS_TABLE, "insert"),
}


def _reject(
    *,
    reject_reason: str,
    failed_rules: list[str],
    fields: dict[str, Any],
    reject_source: str,
    operation: str,
    table: str = ALERTS_TABLE,
) -> FirewallOutcome:
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
    return FirewallOutcome(
        passed=False,
        reject_reason=reject_reason,
        failed_rules=failed_rules,
        forced_log_status=None,
        page_role_verdict=None,
        notes={"table": table, "kind": failed_rules[:1]},
    )


def _semantic_failures(kind: str, fields: dict[str, Any]) -> list[str]:
    failed: list[str] = []
    if kind == "rule_create" and not fields.get("user_id"):
        failed.append("user_id_required")

    alert_type = fields.get("alert_type")
    if alert_type is not None and alert_type not in ALERT_TYPES:
        failed.append("alert_type_invalid")
    if kind == "rule_create" and alert_type is None:
        failed.append("alert_type_required")

    channel = fields.get("channel")
    if channel is not None and channel not in ALERT_CHANNELS:
        failed.append("channel_invalid")

    webhook_url = fields.get("webhook_url")
    if channel == "webhook":
        if not (isinstance(webhook_url, str) and webhook_url.startswith("https://")):
            failed.append("webhook_url_https_required")
    elif webhook_url is not None and channel is not None:
        failed.append("webhook_url_only_for_webhook_channel")

    threshold_pct = fields.get("threshold_pct")
    if threshold_pct is not None:
        try:
            value = float(threshold_pct)
        except (TypeError, ValueError):
            failed.append("threshold_pct_invalid")
        else:
            if not 0 < value <= 100:
                failed.append("threshold_pct_out_of_range")

    cooldown = fields.get("cooldown_minutes")
    if cooldown is not None:
        try:
            minutes = int(cooldown)
        except (TypeError, ValueError):
            failed.append("cooldown_invalid")
        else:
            if minutes < 0 or minutes > 10_080:
                failed.append("cooldown_out_of_range")
    return failed


def _event_semantic_failures(kind: str, fields: dict[str, Any]) -> list[str]:
    failed: list[str] = []
    if kind == "event_create":
        if not fields.get("alert_id"):
            failed.append("alert_id_required")
        message = fields.get("message")
        if not (isinstance(message, str) and message.strip()):
            failed.append("message_required")
        severity = fields.get("severity")
        if severity is not None and severity not in EVENT_SEVERITIES:
            failed.append("severity_invalid")
        sent_via = fields.get("sent_via")
        if sent_via is not None and sent_via not in ALERT_CHANNELS:
            failed.append("sent_via_invalid")
        for numeric_key in ("old_value", "new_value", "change_pct"):
            value = fields.get(numeric_key)
            if value is None:
                continue
            try:
                float(value)
            except (TypeError, ValueError):
                failed.append(f"{numeric_key}_invalid")

    if kind == "rule_trigger":
        if not fields.get("last_triggered_at"):
            failed.append("last_triggered_at_required")
        count = fields.get("trigger_count")
        try:
            if count is None or int(count) < 1:
                failed.append("trigger_count_invalid")
        except (TypeError, ValueError):
            failed.append("trigger_count_invalid")
    return failed


def authorize_alert_write(
    fields: dict[str, Any],
    *,
    kind: str,
    reject_source: str = "alerts_write",
) -> FirewallOutcome:
    """Authorize an alerts-domain write: kind allowlist + semantics, then sign."""
    allowlist = ALERT_WRITE_ALLOWLIST.get(kind)
    table, operation = _KIND_TARGETS.get(kind, (ALERTS_TABLE, "insert"))
    if allowlist is None:
        return _reject(
            reject_reason=REJECT_UNKNOWN_ALERT_KIND,
            failed_rules=[f"kind:{kind}"],
            fields=fields,
            reject_source=reject_source,
            operation=operation,
            table=table,
        )

    extra = sorted(set(fields) - allowlist)
    if extra:
        return _reject(
            reject_reason=REJECT_ALERT_FIELD_NOT_ALLOWED,
            failed_rules=[f"field:{name}" for name in extra],
            fields=fields,
            reject_source=reject_source,
            operation=operation,
            table=table,
        )

    failed = _semantic_failures(kind, fields) if table == ALERTS_TABLE else []
    failed += _event_semantic_failures(kind, fields)
    if failed:
        return _reject(
            reject_reason=REJECT_ALERT_SEMANTICS,
            failed_rules=failed,
            fields=fields,
            reject_source=reject_source,
            operation=operation,
            table=table,
        )

    passed, contract_failed, reason = _validate_contract_subset(table, fields)
    if not passed:
        return _reject(
            reject_reason=reason or "contract_violation",
            failed_rules=contract_failed,
            fields=fields,
            reject_source=reject_source,
            operation=operation,
            table=table,
        )

    signed_record = _sign_fields(table, operation, fields)
    if signed_record is None:
        return _reject(
            reject_reason="signing_unavailable",
            failed_rules=["signing_secret_missing"],
            fields=fields,
            reject_source=reject_source,
            operation=operation,
            table=table,
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
