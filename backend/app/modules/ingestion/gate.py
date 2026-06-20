"""Backward-compatible re-exports; decision logic lives in data_firewall.rules."""

from __future__ import annotations

from app.modules.data_firewall.rules import (
    MAX_CURRENCY_RAW_LEN,
    SKIP_CURRENCY_COUNTRY_MISMATCH,
    SKIP_CURRENCY_RAW_TOO_LONG,
    SKIP_MISSING_NAME_OR_CURRENCY,
    SKIP_PRICE_NOT_POSITIVE,
    CurrencyResolver,
    GateOutcome,
    evaluate_ecommerce_rules,
)

evaluate_gate = evaluate_ecommerce_rules

__all__ = [
    "MAX_CURRENCY_RAW_LEN",
    "SKIP_CURRENCY_COUNTRY_MISMATCH",
    "SKIP_CURRENCY_RAW_TOO_LONG",
    "SKIP_MISSING_NAME_OR_CURRENCY",
    "SKIP_PRICE_NOT_POSITIVE",
    "CurrencyResolver",
    "GateOutcome",
    "evaluate_gate",
]
