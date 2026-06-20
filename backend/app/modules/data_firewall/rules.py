"""E-commerce validation rules (verbatim port of ingestion gate 5-check logic)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.dimensions import DimCountry, DimMarketplace

MAX_CURRENCY_RAW_LEN = 50

SKIP_MISSING_NAME_OR_CURRENCY = "missing_name_or_currency"
SKIP_CURRENCY_RAW_TOO_LONG = "currency_raw_too_long"
SKIP_CURRENCY_COUNTRY_MISMATCH = "currency_country_mismatch"
SKIP_PRICE_NOT_POSITIVE = "price_not_positive"


class _ExtractedLike(Protocol):
    product_name: str | None
    title: str | None
    price: float | None
    currency: str | None
    currency_raw: str | None


@dataclass(frozen=True)
class GateOutcome:
    """Result of the 5-check e-commerce rules (legacy gate shape)."""

    product_name_ok: bool
    price_ok: bool
    currency_ok: bool
    currency_raw_sane_ok: bool
    currency_country_match_ok: bool
    skip_reason: str | None
    forced_log_status: str | None

    @property
    def passed(self) -> bool:
        return (
            self.product_name_ok
            and self.price_ok
            and self.currency_ok
            and self.currency_raw_sane_ok
            and self.currency_country_match_ok
        )


class CurrencyResolver:
    """Marketplace -> allowed-currency whitelist resolver with per-instance memo."""

    def __init__(self, db: Session) -> None:
        self._db = db
        self._cache: dict[UUID, frozenset[str]] = {}

    def whitelist_for(self, marketplace_id: UUID) -> frozenset[str]:
        cached = self._cache.get(marketplace_id)
        if cached is not None:
            return cached

        marketplace = self._db.get(DimMarketplace, marketplace_id)
        if marketplace is None:
            self._cache[marketplace_id] = frozenset()
            return frozenset()

        allowed: set[str] = set()
        country_code = (marketplace.country_code or "").strip().upper()
        if country_code:
            country = self._db.execute(
                select(DimCountry).where(DimCountry.country_code == country_code)
            ).scalar_one_or_none()
            if country is not None:
                country_currency = getattr(country, "currency_code", None) or getattr(
                    country, "main_currency_code", None
                )
                if isinstance(country_currency, str) and len(country_currency.strip()) == 3:
                    allowed.add(country_currency.strip().upper())

        allowed.update({"EUR", "USD"})
        mp_currency = getattr(marketplace, "currency_code", None)
        if isinstance(mp_currency, str) and len(mp_currency.strip()) == 3:
            allowed.add(mp_currency.strip().upper())

        config = getattr(marketplace, "scraper_config", None) or {}
        extra = config.get("allowed_currencies") if isinstance(config, dict) else None
        if isinstance(extra, list):
            for code in extra:
                if isinstance(code, str) and len(code.strip()) == 3:
                    allowed.add(code.strip().upper())

        result = frozenset(allowed)
        self._cache[marketplace_id] = result
        return result

    def matches(self, marketplace_id: UUID, currency: str | None) -> bool:
        whitelist = self.whitelist_for(marketplace_id)
        if not whitelist:
            return True
        if not currency:
            return False
        return currency.strip().upper() in whitelist


def evaluate_ecommerce_rules(
    data: _ExtractedLike,
    *,
    marketplace_id: UUID,
    currency_resolver: CurrencyResolver,
) -> GateOutcome:
    """Run the 5-check persistence gate on an ExtractedProduct payload."""
    product_name_ok = bool(
        data is not None
        and (
            getattr(data, "product_name", None)
            or getattr(data, "title", None)
        ),
    )
    curr_raw = getattr(data, "currency", None)
    currency_raw_text = getattr(data, "currency_raw", None) or ""
    currency_ok = curr_raw is not None and str(curr_raw).strip() != ""
    price = getattr(data, "price", None)
    price_ok = price is not None and price > 0
    currency_raw_sane_ok = len(currency_raw_text) < MAX_CURRENCY_RAW_LEN
    currency_country_match_ok = currency_resolver.matches(marketplace_id, curr_raw)

    skip_reason: str | None = None
    forced_log_status: str | None = None
    passed = (
        product_name_ok
        and price_ok
        and currency_ok
        and currency_raw_sane_ok
        and currency_country_match_ok
    )
    if not passed:
        if not product_name_ok or not currency_ok:
            skip_reason = SKIP_MISSING_NAME_OR_CURRENCY
        elif not price_ok:
            skip_reason = SKIP_PRICE_NOT_POSITIVE
        elif not currency_raw_sane_ok:
            skip_reason = SKIP_CURRENCY_RAW_TOO_LONG
            forced_log_status = "currency_rejected"
        elif not currency_country_match_ok:
            skip_reason = SKIP_CURRENCY_COUNTRY_MISMATCH
            forced_log_status = "currency_rejected"

    return GateOutcome(
        product_name_ok=product_name_ok,
        price_ok=price_ok,
        currency_ok=currency_ok,
        currency_raw_sane_ok=currency_raw_sane_ok,
        currency_country_match_ok=currency_country_match_ok,
        skip_reason=skip_reason,
        forced_log_status=forced_log_status,
    )
