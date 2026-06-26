"""Convert scraped local prices to EUR using fact_currency_rate (scrape-day snapshot)."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.facts import FactCurrencyRate

_PRICE_EUR_QUANT = Decimal("0.01")

# Deterministic pick when multiple sources exist for the same date_id + currency_code.
_RATE_SOURCE_PRIORITY: tuple[str, ...] = (
    "ecb",
    "openexchangerates",
    "cbr",
    "nbu",
    "nbk",
    "nbb",
    "cbu",
    "nbg",
    "cba",
    "cbar",
    "custom",
)


def _quantize_price_eur(value: Decimal) -> Decimal:
    """Mirror display conversion rounding (scale 2, half-up)."""
    return value.quantize(_PRICE_EUR_QUANT, rounding=ROUND_HALF_UP)


def _source_rank(source: str) -> int:
    normalized = (source or "").strip().lower()
    try:
        return _RATE_SOURCE_PRIORITY.index(normalized)
    except ValueError:
        return len(_RATE_SOURCE_PRIORITY)


def _fetch_rate_to_eur(
    db: Session,
    *,
    date_id: int,
    currency_code: str,
) -> Decimal | None:
    """Operational read on the producer sync session for one scrape-day rate."""
    rows = db.execute(
        select(FactCurrencyRate.rate_to_eur, FactCurrencyRate.source).where(
            FactCurrencyRate.date_id == date_id,
            FactCurrencyRate.currency_code == currency_code,
        ),
    ).all()
    if not rows:
        return None
    best = min(rows, key=lambda row: _source_rank(str(row.source)))
    return Decimal(str(best.rate_to_eur))


def resolve_price_eur(
    *,
    price: float | Decimal,
    currency_code: str,
    date_id: int,
    db: Session,
) -> Decimal | None:
    """Return EUR equivalent for a scraped price, or None when no rate exists.

    EUR-base listings use the local price directly (no fact_currency_rate row).
    Non-EUR listings multiply by rate_to_eur for the scrape-day date_id.
    """
    code = (currency_code or "").strip().upper()
    if not code:
        return None

    price_dec = price if isinstance(price, Decimal) else Decimal(str(price))

    if code == "EUR":
        return _quantize_price_eur(price_dec)

    rate_to_eur = _fetch_rate_to_eur(db, date_id=date_id, currency_code=code)
    if rate_to_eur is None:
        return None

    return _quantize_price_eur(price_dec * rate_to_eur)


__all__ = ["resolve_price_eur"]
