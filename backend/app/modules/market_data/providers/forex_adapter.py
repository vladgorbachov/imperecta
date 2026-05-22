"""Forex providers: open.er-api primary, Frankfurter fallback."""

import logging
from datetime import datetime, timezone
from decimal import Decimal

import httpx

from app.config import Settings
from app.modules.market_data.dto import NormalizedForex
from app.modules.market_data.providers.base import ForexProviderAdapter

logger = logging.getLogger(__name__)
OPEN_ER_FALLBACK_URL = "https://open.er-api.com/v6/latest/EUR"
FRANKFURTER_FALLBACK_URL = "https://api.frankfurter.app/latest?from=EUR"


class ForexOpenErAdapter(ForexProviderAdapter):
    """open.er-api adapter. Normalizes to NormalizedForex."""

    def __init__(self, base_url: str | None = None, timeout: float = 15.0):
        self.base_url = base_url or OPEN_ER_FALLBACK_URL
        self.timeout = timeout

    async def fetch(self) -> list[NormalizedForex]:
        """Fetch latest rates from open.er-api and normalize."""
        refreshed_at = datetime.now(timezone.utc)
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(self.base_url)
            resp.raise_for_status()
            data = resp.json()

        if data.get("result") not in ("success", None):
            logger.warning("open.er-api response error: %s", data.get("error-type"))
            return []
        if "rates" not in data:
            logger.warning("open.er-api response missing 'rates': %s", data)
            return []
        base = data.get("base") or data.get("base_code")
        if not base:
            logger.warning("Forex response missing base/base_code: %s", data)
            return []

        items: list[NormalizedForex] = []
        rates = data["rates"]
        for quote, rate in rates.items():
            try:
                rate_val = Decimal(str(rate))
                spread = Decimal("0.0001")
                items.append(
                    NormalizedForex(
                        symbol=f"{base}/{quote}",
                        bid=rate_val,
                        ask=rate_val + spread,
                        spread=spread,
                        change_24h=None,
                        refreshed_at=refreshed_at,
                    )
                )
            except Exception as error:
                logger.warning("Parse forex %s/%s: %s", base, quote, error)
                continue

        logger.info("Forex adapter fetched %d pairs", len(items))
        return items


class ForexFrankfurterAdapter(ForexProviderAdapter):
    """Frankfurter API adapter. Normalizes to NormalizedForex."""

    def __init__(self, base_url: str | None = None, timeout: float = 15.0):
        self.base_url = base_url or FRANKFURTER_FALLBACK_URL
        self.timeout = timeout

    async def fetch(self) -> list[NormalizedForex]:
        refreshed_at = datetime.now(timezone.utc)
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(self.base_url)
            resp.raise_for_status()
            data = resp.json()

        rates = data.get("rates")
        base = data.get("base")
        if not isinstance(rates, dict) or not base:
            logger.warning("Frankfurter response invalid: %s", data)
            return []

        items: list[NormalizedForex] = []
        for quote, rate in rates.items():
            try:
                rate_val = Decimal(str(rate))
                spread = Decimal("0.0001")
                items.append(
                    NormalizedForex(
                        symbol=f"{base}/{quote}",
                        bid=rate_val,
                        ask=rate_val + spread,
                        spread=spread,
                        change_24h=None,
                        refreshed_at=refreshed_at,
                    )
                )
            except Exception as error:
                logger.warning("Parse forex %s/%s: %s", base, quote, error)
        return items


class ForexUnifiedAdapter(ForexProviderAdapter):
    """Unified forex adapter: configured source -> open.er fallback -> Frankfurter fallback."""

    def __init__(self, timeout: float = 15.0):
        configured = (Settings().market_data_forex_url or "").strip()
        self.timeout = timeout
        self._configured = configured

    async def fetch(self) -> list[NormalizedForex]:
        adapters: list[ForexProviderAdapter] = []
        if self._configured:
            if "open.er-api.com" in self._configured:
                adapters.append(ForexOpenErAdapter(base_url=self._configured, timeout=self.timeout))
            elif "frankfurter.app" in self._configured:
                adapters.append(ForexFrankfurterAdapter(base_url=self._configured, timeout=self.timeout))
            else:
                adapters.append(ForexOpenErAdapter(base_url=self._configured, timeout=self.timeout))

        adapters.extend(
            [
                ForexOpenErAdapter(timeout=self.timeout),
                ForexFrankfurterAdapter(timeout=self.timeout),
            ]
        )

        for adapter in adapters:
            try:
                data = await adapter.fetch()
                if data:
                    return data
            except Exception as error:
                logger.warning("Forex provider %s failed: %s", adapter.__class__.__name__, error)
        return []
