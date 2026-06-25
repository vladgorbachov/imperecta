"""Data firewall entrypoints — pure validation, sign on pass."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Protocol
from uuid import UUID

import structlog

from app.modules.data_firewall.contracts import (
    FACT_TABLE_CONTRACTS,
    ColumnContract,
    extract_locator,
)
from app.modules.data_firewall.reject_store import write_reject_data_isolated
from app.modules.data_firewall.rules import (
    SKIP_CURRENCY_COUNTRY_MISMATCH,
    SKIP_CURRENCY_RAW_TOO_LONG,
    SKIP_MISSING_NAME_OR_CURRENCY,
    SKIP_PRICE_NOT_POSITIVE,
    CurrencyResolver,
    GateOutcome,
    evaluate_ecommerce_rules,
)
from app.modules.data_firewall.signing import SignedRecord, sign

slog = structlog.get_logger(__name__)

REJECT_NOT_A_PRODUCT_PAGE = "not_a_product_page"
REJECT_CONTRACT_VIOLATION = "contract_violation"
REJECT_FAKE_DEFAULT = "fake_default"
REJECT_SIGNING_UNAVAILABLE = "signing_unavailable"
FORCED_NOT_A_PRODUCT = "not_a_product"


class _RecordLike(Protocol):
    product_name: str | None
    title: str | None
    price: float | None
    currency: str | None
    currency_raw: str | None
    page_role: str | None


@dataclass(frozen=True)
class FirewallOutcome:
    """Firewall decision for one record."""

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
    signed_record: SignedRecord | None = None

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


def _numeric_fits(value: float | int, precision: int | None, scale: int | None) -> bool:
    if precision is None or scale is None:
        return True
    try:
        dec = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return False
    sign, digits, exponent = dec.as_tuple()
    if exponent >= 0:
        int_digits = len(digits)
        frac_digits = 0
    else:
        frac_digits = -exponent
        int_digits = max(0, len(digits) - frac_digits)
    total_digits = int_digits + frac_digits
    return total_digits <= precision and frac_digits <= scale


def _validate_against_contract(
    record: dict[str, Any],
    contract: dict[str, ColumnContract],
) -> tuple[bool, list[str], str | None]:
    """Enforce per-column contract for fields present in the persist payload."""
    failed: list[str] = []
    for column_name, value in record.items():
        spec = contract.get(column_name)
        if spec is None:
            continue
        if value is None:
            if not spec.get("nullable", True):
                failed.append(f"null:{column_name}")
            continue

        expected_type = spec.get("type")
        if expected_type == "string" and not isinstance(value, str):
            failed.append(f"type:{column_name}")
            continue
        if expected_type in {"integer", "smallint"} and not isinstance(value, int):
            failed.append(f"type:{column_name}")
            continue
        if expected_type == "boolean" and not isinstance(value, bool):
            failed.append(f"type:{column_name}")
            continue
        if expected_type == "numeric" and not isinstance(value, (int, float)):
            failed.append(f"type:{column_name}")
            continue
        if expected_type == "uuid" and not isinstance(value, (UUID, str)):
            failed.append(f"type:{column_name}")
            continue
        if expected_type == "datetime" and not isinstance(value, (datetime, str)):
            failed.append(f"type:{column_name}")
            continue

        if expected_type == "string" and isinstance(value, str):
            max_len = spec.get("max_len")
            if max_len is not None and len(value) > max_len:
                failed.append(f"length:{column_name}")
        if expected_type == "numeric" and isinstance(value, (int, float)):
            if not _numeric_fits(value, spec.get("precision"), spec.get("scale")):
                failed.append(f"precision:{column_name}")
            if isinstance(value, (int, float)) and value <= 0:
                if column_name in {"price", "price_usd", "rate_to_eur", "rate_to_usd"}:
                    failed.append(f"non_positive:{column_name}")

        check_values = spec.get("check_values")
        if check_values and str(value) not in check_values:
            failed.append(f"check:{column_name}")

    if failed:
        return False, failed, REJECT_CONTRACT_VIOLATION
    return True, [], None


def _sign_fields(
    table: str,
    operation: str,
    fields: dict[str, Any],
) -> SignedRecord | None:
    locator = extract_locator(table, fields)
    signature = sign(
        table=table,
        operation=operation,
        fields=fields,
        locator=locator,
    )
    if signature is None:
        return None
    return SignedRecord(
        table=table,
        operation=operation,
        locator=locator,
        fields=fields,
        signature=signature,
    )


def _extract_snapshot(record: _RecordLike) -> dict[str, Any]:
    """Minimal extract snapshot for firewall rejects before persist fields exist."""
    return {
        "product_name": getattr(record, "product_name", None),
        "title": getattr(record, "title", None),
        "price": getattr(record, "price", None),
        "currency": getattr(record, "currency", None),
        "currency_raw": getattr(record, "currency_raw", None),
        "page_role": getattr(record, "page_role", None),
    }


def evaluate_ecommerce(
    record: _RecordLike,
    *,
    marketplace_id: UUID,
    currency_resolver: CurrencyResolver,
    page_role: str | None = None,
    persist_fields: dict[str, Any] | None = None,
    table: str = "fact_price",
    db: Any | None = None,
    reject_source: str = "ecommerce_scrape",
    listing_id: UUID | None = None,
) -> FirewallOutcome:
    """Validate e-commerce extract; sign persist_fields on full pass."""
    rule_outcome = evaluate_ecommerce_rules(
        record,
        marketplace_id=marketplace_id,
        currency_resolver=currency_resolver,
    )
    role = page_role if page_role is not None else getattr(record, "page_role", None)
    page_role_verdict = _page_role_verdict(role)

    failed_rules = _failed_rules_from_gate(rule_outcome)
    reject_reason = rule_outcome.skip_reason
    forced_log_status = rule_outcome.forced_log_status
    passed = rule_outcome.passed

    if passed and role in ("listing", "hub"):
        passed = False
        reject_reason = FORCED_NOT_A_PRODUCT
        forced_log_status = FORCED_NOT_A_PRODUCT
        failed_rules = ["page_role_not_product"]
        slog.info(
            "data_firewall_rejected_nonproduct",
            marketplace_id=str(marketplace_id),
            role=role,
            page_role_verdict=page_role_verdict,
        )
    elif role == "unknown":
        slog.info(
            "data_firewall_page_role_unknown",
            marketplace_id=str(marketplace_id),
            role=role,
            page_role_verdict=page_role_verdict,
        )
    elif role is not None:
        slog.info(
            "data_firewall_page_role_observed",
            marketplace_id=str(marketplace_id),
            role=role,
            would_block=False,
            page_role_verdict=page_role_verdict,
        )

    signed_record: SignedRecord | None = None

    if passed and persist_fields is not None:
        contract = FACT_TABLE_CONTRACTS.get(table, {})
        contract_ok, contract_failed, contract_reason = _validate_against_contract(
            persist_fields,
            contract,
        )
        if not contract_ok:
            passed = False
            reject_reason = contract_reason
            failed_rules = contract_failed
            forced_log_status = "currency_rejected"
        else:
            signed_record = _sign_fields(table, "insert", persist_fields)
            if signed_record is None:
                passed = False
                reject_reason = REJECT_SIGNING_UNAVAILABLE
                failed_rules = ["signing_secret_missing"]
                forced_log_status = "persist_failed"

    if not passed and db is not None:
        payload = persist_fields if persist_fields is not None else _extract_snapshot(record)
        write_reject_data_isolated(
            source=reject_source,
            table_target=table,
            reject_reason=reject_reason or "data_firewall_reject",
            failed_rules=failed_rules,
            raw_payload=payload,
            rejected_by="data_firewall",
            marketplace_id=marketplace_id,
            listing_id=listing_id,
            signature_present=False,
            operation="insert",
        )

    return FirewallOutcome(
        passed=passed,
        reject_reason=reject_reason,
        failed_rules=failed_rules,
        forced_log_status=forced_log_status,
        page_role_verdict=page_role_verdict,
        notes={"page_role": role},
        product_name_ok=rule_outcome.product_name_ok,
        price_ok=rule_outcome.price_ok,
        currency_ok=rule_outcome.currency_ok,
        currency_raw_sane_ok=rule_outcome.currency_raw_sane_ok,
        currency_country_match_ok=rule_outcome.currency_country_match_ok,
        signed_record=signed_record,
    )


def evaluate_market(
    record: dict[str, Any],
    *,
    table: str,
    db: Any | None = None,
    reject_source: str = "market_data",
) -> FirewallOutcome:
    """Market rail: contract validation + sign on pass."""
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
    signed_record: SignedRecord | None = None

    if passed:
        signed_record = _sign_fields(table, "insert", record)
        if signed_record is None:
            passed = False
            reject_reason = REJECT_SIGNING_UNAVAILABLE
            failed_rules = ["signing_secret_missing"]

    if not passed and db is not None:
        write_reject_data_isolated(
            source=reject_source,
            table_target=table,
            reject_reason=reject_reason or "data_firewall_reject",
            failed_rules=failed_rules,
            raw_payload=record,
            rejected_by="data_firewall",
            signature_present=False,
            operation="insert",
        )

    return FirewallOutcome(
        passed=passed,
        reject_reason=reject_reason,
        failed_rules=failed_rules,
        forced_log_status=None,
        page_role_verdict=None,
        notes={"table": table},
        signed_record=signed_record,
    )


__all__ = [
    "FORCED_NOT_A_PRODUCT",
    "FirewallOutcome",
    "REJECT_CONTRACT_VIOLATION",
    "REJECT_FAKE_DEFAULT",
    "REJECT_NOT_A_PRODUCT_PAGE",
    "REJECT_SIGNING_UNAVAILABLE",
    "evaluate_ecommerce",
    "evaluate_market",
    "SKIP_CURRENCY_COUNTRY_MISMATCH",
    "SKIP_CURRENCY_RAW_TOO_LONG",
    "SKIP_MISSING_NAME_OR_CURRENCY",
    "SKIP_PRICE_NOT_POSITIVE",
]
