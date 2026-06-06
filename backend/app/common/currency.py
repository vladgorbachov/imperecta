"""Display-currency conversion for product prices.

Uses the same source as the markets banner: ``fact_currency_rate`` (newest
``date_id`` = current rate). Each row stores the value of one unit of the
currency in EUR (``rate_to_eur``) and in USD (``rate_to_usd``), so conversion is
a direct multiplication. No fallback/mock rates are produced — when a rate is
missing the converter returns ``None`` and callers must surface the local price.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.facts import FactCurrencyRate

DISPLAY_LOCAL = "local"
DISPLAY_EUR = "EUR"
DISPLAY_USD = "USD"
DISPLAY_CURRENCIES: tuple[str, ...] = (DISPLAY_LOCAL, DISPLAY_EUR, DISPLAY_USD)


def normalize_display_currency(value: str | None) -> str:
    """Coerce an arbitrary query value to a supported display-currency mode."""
    if not value:
        return DISPLAY_LOCAL
    upper = value.strip().upper()
    if upper == DISPLAY_EUR:
        return DISPLAY_EUR
    if upper == DISPLAY_USD:
        return DISPLAY_USD
    return DISPLAY_LOCAL


@dataclass(frozen=True)
class _Rate:
    """Value of one unit of a currency, expressed in EUR and in USD."""

    to_eur: float
    to_usd: float


class CurrencyConverter:
    """Convert local prices to EUR/USD using the latest stored FX rates."""

    def __init__(self, rates: dict[str, _Rate], usd_per_eur: float | None) -> None:
        self._rates = rates
        self._usd_per_eur = usd_per_eur

    @classmethod
    async def load_latest(cls, db: AsyncSession) -> "CurrencyConverter":
        """Load FX rates from the same source the markets banner uses.

        Mirrors the ``/markets/forex`` precedence: the persisted snapshot in
        ``fact_currency_rate`` first, falling back to the live forex feed when
        the table has not been ingested yet.
        """
        rates = await cls._load_from_db(db)
        if not rates:
            rates = await cls._load_from_live()
        return cls(rates, cls._derive_usd_per_eur(rates))

    @staticmethod
    async def _load_from_db(db: AsyncSession) -> dict[str, _Rate]:
        """Newest snapshot from ``fact_currency_rate`` (value of 1 unit)."""
        latest_date = await db.scalar(select(func.max(FactCurrencyRate.date_id)))
        rates: dict[str, _Rate] = {}
        if latest_date is None:
            return rates
        result = await db.execute(
            select(
                FactCurrencyRate.currency_code,
                FactCurrencyRate.rate_to_eur,
                FactCurrencyRate.rate_to_usd,
            ).where(FactCurrencyRate.date_id == latest_date)
        )
        for code, to_eur, to_usd in result.all():
            key = (code or "").strip().upper()
            if not key or key in rates:
                continue
            rates[key] = _Rate(to_eur=float(to_eur), to_usd=float(to_usd))
        return rates

    @staticmethod
    async def _load_from_live() -> dict[str, _Rate]:
        """Live EUR-based feed (same call as the banner fallback).

        Each pair is ``EUR/<quote>`` with ``rate`` = quote units per 1 EUR, so
        one unit of the quote currency is worth ``1 / rate`` EUR.
        """
        from app.modules.market_data.service import fetch_forex_rates

        try:
            raw = await fetch_forex_rates("EUR")
        except Exception:  # noqa: BLE001 - missing rates must not break price listing
            return {}

        pairs: dict[str, float] = {}
        for row in raw or []:
            pair = str(row.get("pair", "")).strip()
            if "/" not in pair:
                continue
            quote = pair.split("/")[-1].strip().upper()
            try:
                rate = float(row.get("rate", 0) or 0)
            except (TypeError, ValueError):
                continue
            if len(quote) == 3 and rate > 0:
                pairs[quote] = rate

        usd_per_eur = pairs.get(DISPLAY_USD)
        rates: dict[str, _Rate] = {}
        for quote, rate in pairs.items():
            to_eur = 1.0 / rate
            to_usd = (usd_per_eur / rate) if usd_per_eur else to_eur
            rates[quote] = _Rate(to_eur=to_eur, to_usd=to_usd)
        return rates

    @staticmethod
    def _derive_usd_per_eur(rates: dict[str, _Rate]) -> float | None:
        """USD value of 1 EUR, derived from any currency row (EUR has no row)."""
        usd_row = rates.get(DISPLAY_USD)
        if usd_row and usd_row.to_eur > 0:
            return 1.0 / usd_row.to_eur
        for rate in rates.values():
            if rate.to_eur > 0:
                return rate.to_usd / rate.to_eur
        return None

    @property
    def has_rates(self) -> bool:
        return bool(self._rates)

    def _factor(self, currency: str, target: str) -> float | None:
        """Multiplier to convert 1 unit of ``currency`` into ``target``."""
        cur = (currency or "").strip().upper()
        if not cur or target not in (DISPLAY_EUR, DISPLAY_USD):
            return None
        if cur == target:
            return 1.0
        if cur == DISPLAY_EUR:
            # target is USD here (EUR==EUR handled above).
            return self._usd_per_eur
        if cur == DISPLAY_USD:
            # target is EUR here.
            usd_row = self._rates.get(DISPLAY_USD)
            if usd_row and usd_row.to_eur > 0:
                return usd_row.to_eur
            return (1.0 / self._usd_per_eur) if self._usd_per_eur else None
        rate = self._rates.get(cur)
        if rate is None:
            return None
        return rate.to_eur if target == DISPLAY_EUR else rate.to_usd

    def convert(
        self,
        amount: float | Decimal | None,
        currency: str | None,
        target: str,
    ) -> float | None:
        """Convert ``amount`` from ``currency`` to ``target`` (EUR/USD).

        Returns ``None`` when the amount is missing or no rate is available.
        """
        if amount is None:
            return None
        factor = self._factor(currency or "", target)
        if factor is None or factor <= 0:
            return None
        return float(amount) * factor


def display_price_fields(
    amount: float | Decimal | None,
    currency: str | None,
    display_currency: str,
    converter: CurrencyConverter | None,
) -> tuple[float | None, str | None, bool]:
    """Compute ``(display_price, display_currency, conversion_available)``.

    For local mode (or when conversion is unavailable) returns no converted
    value; the caller keeps showing the local price.
    """
    target = normalize_display_currency(display_currency)
    if target == DISPLAY_LOCAL or amount is None or converter is None:
        return None, None, False
    converted = converter.convert(amount, currency, target)
    if converted is None:
        return None, None, False
    return round(converted, 2), target, True
