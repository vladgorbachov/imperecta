"""Backward-compatible re-exports; decision logic lives in data_firewall.rules."""

from __future__ import annotations

from app.common.html_parsing import (
    AMBIGUOUS_CURRENCY_SIBLINGS,
    currency_token_is_ambiguous,
)
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


def disambiguate_currency(
    detected: str | None,
    raw_text: str | None,
    whitelist: frozenset[str],
) -> str | None:
    """Resolve a shared currency token against the marketplace whitelist.

    "lei"/"лей" and "kr" map to one code by default (RON, SEK); when that code
    is not allowed for the marketplace but exactly one sibling currency is,
    the sibling is the honest reading (a Moldovan shop's "lei" is MDL). An
    unambiguous token or an in-whitelist detection is returned unchanged.
    """
    if not detected:
        return detected
    code = detected.strip().upper()
    if code in whitelist or not whitelist:
        return detected
    if not currency_token_is_ambiguous(raw_text):
        return detected
    siblings = AMBIGUOUS_CURRENCY_SIBLINGS.get(code, frozenset())
    allowed_siblings = sorted(siblings & whitelist)
    if len(allowed_siblings) == 1:
        return allowed_siblings[0]
    return detected
