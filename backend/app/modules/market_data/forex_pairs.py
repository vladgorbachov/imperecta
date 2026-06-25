"""Forex allowlist pair derivation — rates from DB rows only, never hardcoded."""

from __future__ import annotations

from typing import Any

import structlog

slog = structlog.get_logger(__name__)

# PAIR A/B = units of quote currency B per 1 unit of base currency A.
PAIR_DIRECTION = "units of quote per 1 base (A/B)"

FOREX_PRIMARY_PAIRS: tuple[tuple[str, str], ...] = (
    ("EUR", "USD"),
    ("GBP", "USD"),
    ("USD", "JPY"),
    ("USD", "CHF"),
    ("MDL", "EUR"),
    ("MDL", "USD"),
    ("RON", "EUR"),
    ("RON", "USD"),
    ("PLN", "EUR"),
    ("PLN", "USD"),
    ("TRY", "EUR"),
    ("TRY", "USD"),
)

DEFAULT_FOREX_ALLOWED_CURRENCIES: frozenset[str] = frozenset(
    {"USD", "EUR", "GBP", "JPY", "CHF", "MDL", "RON", "PLN", "TRY"},
)


def build_rate_to_eur_index(currency_rows: list[dict[str, Any]]) -> dict[str, float]:
    """Map currency_code -> EUR value of one unit (EUR identity = 1.0)."""
    index: dict[str, float] = {"EUR": 1.0}
    for row in currency_rows:
        code = str(row.get("currency_code", "")).upper()
        if not code or code == "EUR":
            continue
        rte = row.get("rate_to_eur")
        if rte is None:
            continue
        rate = float(rte)
        if rate > 0:
            index[code] = rate
    return index


def derive_forex_pairs(
    currency_rows: list[dict[str, Any]],
    *,
    include_inverses: bool = True,
) -> list[dict[str, Any]]:
    """Derive configured forex pairs (+ inverses) from per-currency rate_to_eur rows."""
    index = build_rate_to_eur_index(currency_rows)
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    def add_pair(base: str, quote: str) -> None:
        key = (base, quote)
        if key in seen:
            return
        if base not in index or quote not in index:
            slog.debug(
                "forex_pair_omitted",
                base=base,
                quote=quote,
                reason="missing_currency",
            )
            return
        rate = index[base] / index[quote]
        if rate <= 0:
            slog.debug(
                "forex_pair_omitted",
                base=base,
                quote=quote,
                reason="non_positive_rate",
            )
            return
        seen.add(key)
        out.append({
            "symbol": f"{base}/{quote}",
            "base": base,
            "quote": quote,
            "rate": rate,
        })

    for base, quote in FOREX_PRIMARY_PAIRS:
        add_pair(base, quote)
        if include_inverses:
            add_pair(quote, base)

    return out


