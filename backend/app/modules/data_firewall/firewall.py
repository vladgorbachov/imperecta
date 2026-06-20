"""Data firewall entrypoints — pure validation, no mutation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol
from uuid import UUID

import structlog

from app.modules.data_firewall.contracts import FACT_TABLE_CONTRACTS, ColumnContract
from app.modules.data_firewall.rules import (
    SKIP_CURRENCY_COUNTRY_MISMATCH,
    SKIP_CURRENCY_RAW_TOO_LONG,
    SKIP_MISSING_NAME_OR_CURRENCY,
    SKIP_PRICE_NOT_POSITIVE,
    CurrencyResolver,
    GateOutcome,
    evaluate_ecommerce_rules,
)

slog = structlog.get_logger(__name__)


class _RecordLike(Protocol):
    product_name: str | None
    title: str | None
    price: float | None
    currency: str | None
    currency_raw: str | None
    page_role: str | None


@dataclass(frozen=True)
class FirewallOutcome:
    """Firewall decision for one record (no OK-flag in 1.1)."""

    passed: bool
    reject_reason: str | None
    failed_rules: list[str]
    forced_log_status: str | None
    page_role_verdict: str | None
    notes: dict[str, Any] = field(default_factory=dict)
    product_name_ok: bool = False
    price_ok: bool = False
    currency_ok: bool = False
    currency_raw_sane_ok: bool = False
    currency_country_match_ok: bool = False

    @property
    def skip_reason(self) -> str | None:
        """Alias for legacy gate callers."""
        return self.reject_reason


def _failed_rules_from_gate(outcome: GateOutcome) -> list[str]:
    failed: list[str] = []
    if not outcome.product_name_ok:
        failed.append("product_name_ok")
    if not outcome.price_ok:
        failed.append("price_ok")
    if not outcome.currency_ok:
        failed.append("currency_ok")
    if not outcome.currency_raw_sane_ok:
        failed.append("currency_raw_sane_ok")
    if not outcome.currency_country_match_ok:
        failed.append("currency_country_match_ok")
    return failed


def _page_role_verdict(page_role: str | None) -> str | None:
    if page_role is None:
        return None
    if page_role == "product":
        return "product"
    if page_role in ("listing", "hub"):
        return "non_product"
    return "unknown"


def evaluate_ecommerce(
    record: _RecordLike,
    *,
    marketplace_id: UUID,
    currency_resolver: CurrencyResolver,
    page_role: str | None = None,
) -> FirewallOutcome:
    """Validate an e-commerce extract; 1.1 uses only the legacy 5 gate rules."""
    rule_outcome = evaluate_ecommerce_rules(
        record,
        marketplace_id=marketplace_id,
        currency_resolver=currency_resolver,
    )
    role = page_role if page_role is not None else getattr(record, "page_role", None)
    page_role_verdict = _page_role_verdict(role)
    would_block = role is not None and role != "product"
    slog.info(
        "firewall_page_role_observed",
        marketplace_id=str(marketplace_id),
        role=role,
        would_block=would_block,
        page_role_verdict=page_role_verdict,
    )
    return FirewallOutcome(
        passed=rule_outcome.passed,
        reject_reason=rule_outcome.skip_reason,
        failed_rules=_failed_rules_from_gate(rule_outcome),
        forced_log_status=rule_outcome.forced_log_status,
        page_role_verdict=page_role_verdict,
        notes={"would_block_non_product": would_block},
        product_name_ok=rule_outcome.product_name_ok,
        price_ok=rule_outcome.price_ok,
        currency_ok=rule_outcome.currency_ok,
        currency_raw_sane_ok=rule_outcome.currency_raw_sane_ok,
        currency_country_match_ok=rule_outcome.currency_country_match_ok,
    )


def _validate_against_contract(
    record: dict[str, Any],
    contract: dict[str, ColumnContract],
) -> tuple[bool, list[str], str | None]:
    """Structural validation stub for market rails (not wired in 1.1)."""
    failed: list[str] = []
    for column_name, spec in contract.items():
        if column_name not in record:
            if not spec.get("nullable", True):
                failed.append(f"missing:{column_name}")
            continue
        value = record[column_name]
        if value is None and not spec.get("nullable", True):
            failed.append(f"null:{column_name}")
            continue
        if value is None:
            continue
        expected_type = spec.get("type")
        if expected_type == "string" and not isinstance(value, str):
            failed.append(f"type:{column_name}")
        elif expected_type in {"integer", "smallint"} and not isinstance(value, int):
            failed.append(f"type:{column_name}")
        elif expected_type == "boolean" and not isinstance(value, bool):
            failed.append(f"type:{column_name}")
        elif expected_type == "numeric" and not isinstance(value, (int, float)):
            failed.append(f"type:{column_name}")
        check_values = spec.get("check_values")
        if check_values and str(value) not in check_values:
            failed.append(f"check:{column_name}")
    if failed:
        return False, failed, failed[0]
    return True, [], None


def evaluate_market(
    record: dict[str, Any],
    *,
    table: str,
) -> FirewallOutcome:
    """Market-rail stub: validates against the declarative contract only."""
    contract = FACT_TABLE_CONTRACTS.get(table)
    if contract is None:
        return FirewallOutcome(
            passed=False,
            reject_reason="unknown_table",
            failed_rules=["unknown_table"],
            forced_log_status=None,
            page_role_verdict=None,
            notes={"table": table},
        )
    passed, failed_rules, reject_reason = _validate_against_contract(record, contract)
    return FirewallOutcome(
        passed=passed,
        reject_reason=reject_reason,
        failed_rules=failed_rules,
        forced_log_status=None,
        page_role_verdict=None,
        notes={"table": table},
    )


__all__ = [
    "FirewallOutcome",
    "evaluate_ecommerce",
    "evaluate_market",
    "SKIP_CURRENCY_COUNTRY_MISMATCH",
    "SKIP_CURRENCY_RAW_TOO_LONG",
    "SKIP_MISSING_NAME_OR_CURRENCY",
    "SKIP_PRICE_NOT_POSITIVE",
]
