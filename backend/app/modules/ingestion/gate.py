"""PERSISTENCE_GATE — verbatim 5-check ingestion quality gate.

Moved out of ``app.modules.scraper.service`` in ING1 byte-for-byte. The five
checks (product_name_ok, price_ok, currency_ok, currency_raw_sane_ok,
currency_country_match_ok), the ``MAX_CURRENCY_RAW_LEN`` constant, and the
marketplace currency whitelist + country-match helpers all live here so they
can be exercised in isolation and re-used by the Phase 4 user-upload rail.

The klick.ee currency-raw glued-text case is intentionally still rejected by
this gate — the underlying fix is a Phase 5 extractor microdata change, NOT
an ingestion change.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.dimensions import DimCountry, DimMarketplace

# Currency text longer than this is almost certainly glued header/footer text
# caught by merge_and_finalize's fallback currency detection, not a real price
# label.
MAX_CURRENCY_RAW_LEN = 50

# Gate-rejection reasons (machine-readable; mirror the inline log strings).
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
    """Result of evaluating the persistence gate against an ExtractedProduct."""

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
    """Marketplace -> allowed-currency whitelist resolver with per-instance memo.

    Verbatim port of ``GlobalScrapeService._marketplace_currency_whitelist`` /
    ``_currency_matches_marketplace``. EUR and USD are always allowed; the
    marketplace's own ``currency_code``, its ``country_code``-derived primary
    currency, and any ``scraper_config.allowed_currencies`` are unioned in.
    """

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


def evaluate_gate(
    data: _ExtractedLike,
    *,
    marketplace_id: UUID,
    currency_resolver: CurrencyResolver,
) -> GateOutcome:
    """Run the 5-check persistence gate on an ExtractedProduct payload.

    Logic matches the inline block previously in ``GlobalScrapeService.scrape_product``
    byte-for-byte. ``forced_log_status`` is set to ``parse_error`` ONLY when
    the gate rejects for a currency-raw or country-mismatch reason (matches
    the original ``forced_log_status = "parse_error"`` branches).
    """
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
            forced_log_status = "parse_error"
        elif not currency_country_match_ok:
            skip_reason = SKIP_CURRENCY_COUNTRY_MISMATCH
            forced_log_status = "parse_error"

    return GateOutcome(
        product_name_ok=product_name_ok,
        price_ok=price_ok,
        currency_ok=currency_ok,
        currency_raw_sane_ok=currency_raw_sane_ok,
        currency_country_match_ok=currency_country_match_ok,
        skip_reason=skip_reason,
        forced_log_status=forced_log_status,
    )
