"""Forex providers: open.er-api primary, Frankfurter fallback."""

import logging
from datetime import datetime, timezone
from decimal import Decimal

import httpx

from app.config import Settings
from app.modules.market_data.dto import NormalizedForex
from app.modules.market_data.http_config import (
    DEFAULT_MARKET_DATA_TIMEOUT_SECONDS,
    with_transient_retries,
)
from app.modules.market_data.provider_queue import InstrumentProvider, gap_fill_fetch
from app.modules.market_data.providers.base import ForexProviderAdapter

logger = logging.getLogger(__name__)
OPEN_ER_FALLBACK_URL = "https://open.er-api.com/v6/latest/EUR"
FRANKFURTER_FALLBACK_URL = "https://api.frankfurter.app/latest?from=EUR"

FOREX_PROVIDER_OPENEXCHANGERATES = "openexchangerates"
FOREX_PROVIDER_ECB = "ecb"


class ForexOpenErAdapter(ForexProviderAdapter):
    """open.er-api adapter. Normalizes to NormalizedForex."""

    provider_source = FOREX_PROVIDER_OPENEXCHANGERATES

    def __init__(self, base_url: str | None = None, timeout: float = DEFAULT_MARKET_DATA_TIMEOUT_SECONDS):
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
                        provider_source=self.provider_source,
                    )
                )
            except Exception as error:
                logger.warning("Parse forex %s/%s: %s", base, quote, error)
                continue

        logger.info("Forex adapter fetched %d pairs", len(items))
        return items


class ForexFrankfurterAdapter(ForexProviderAdapter):
    """Frankfurter API adapter. Normalizes to NormalizedForex."""

    provider_source = FOREX_PROVIDER_ECB

    def __init__(self, base_url: str | None = None, timeout: float = DEFAULT_MARKET_DATA_TIMEOUT_SECONDS):
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
                        provider_source=self.provider_source,
                    )
                )
            except Exception as error:
                logger.warning("Parse forex %s/%s: %s", base, quote, error)
        return items


class _QueuedForexProvider:
    """Wraps a forex adapter for gap-fill queue (keyed by quote currency code)."""

    def __init__(
        self,
        adapter: ForexProviderAdapter,
        *,
        provider_source: str,
        base: str,
        retry_attempts: int,
    ) -> None:
        self._adapter = adapter
        self._provider_source = provider_source
        self._base = base.upper()
        self._retry_attempts = retry_attempts

    @property
    def provider_source(self) -> str:
        return self._provider_source

    async def fetch_instruments(self, requested: frozenset[str]) -> dict[str, NormalizedForex]:
        if not requested:
            return {}

        items = await with_transient_retries(
            self._adapter.fetch,
            retry_attempts=self._retry_attempts,
            label=self._adapter.__class__.__name__,
        )
        base_prefix = f"{self._base}/"
        out: dict[str, NormalizedForex] = {}
        for dto in items:
            pair = dto.symbol.upper()
            if not pair.startswith(base_prefix):
                continue
            quote = pair.split("/")[-1].strip().upper()
            if quote not in requested or len(quote) != 3:
                continue
            out[quote] = dto.model_copy(update={"provider_source": self._provider_source})
        return out


def build_forex_queue_providers(
    *,
    timeout: float,
    retry_attempts: int,
    base: str = "EUR",
) -> list[_QueuedForexProvider]:
    """Ordered forex providers mirroring legacy ForexUnifiedAdapter precedence."""
    configured = (Settings().market_data_forex_url or "").strip()
    providers: list[_QueuedForexProvider] = []

    if configured:
        if "open.er-api.com" in configured:
            providers.append(
                _QueuedForexProvider(
                    ForexOpenErAdapter(base_url=configured, timeout=timeout),
                    provider_source=FOREX_PROVIDER_OPENEXCHANGERATES,
                    base=base,
                    retry_attempts=retry_attempts,
                ),
            )
        elif "frankfurter.app" in configured:
            providers.append(
                _QueuedForexProvider(
                    ForexFrankfurterAdapter(base_url=configured, timeout=timeout),
                    provider_source=FOREX_PROVIDER_ECB,
                    base=base,
                    retry_attempts=retry_attempts,
                ),
            )
        else:
            providers.append(
                _QueuedForexProvider(
                    ForexOpenErAdapter(base_url=configured, timeout=timeout),
                    provider_source=FOREX_PROVIDER_OPENEXCHANGERATES,
                    base=base,
                    retry_attempts=retry_attempts,
                ),
            )

    providers.extend(
        [
            _QueuedForexProvider(
                ForexOpenErAdapter(timeout=timeout),
                provider_source=FOREX_PROVIDER_OPENEXCHANGERATES,
                base=base,
                retry_attempts=retry_attempts,
            ),
            _QueuedForexProvider(
                ForexFrankfurterAdapter(timeout=timeout),
                provider_source=FOREX_PROVIDER_ECB,
                base=base,
                retry_attempts=retry_attempts,
            ),
        ],
    )
    return providers


async def fetch_forex_normalized(
    *,
    base: str = "EUR",
    timeout: float = DEFAULT_MARKET_DATA_TIMEOUT_SECONDS,
    retry_attempts: int = 0,
    requested_currencies: frozenset[str] | None = None,
) -> list[NormalizedForex]:
    """Fetch forex via cross-provider gap-fill queue."""
    if requested_currencies is None:
        requested_currencies = Settings().forex_allowed_currency_set - {"EUR"}

    providers = build_forex_queue_providers(
        timeout=timeout,
        retry_attempts=retry_attempts,
        base=base,
    )
    result = await gap_fill_fetch(providers, requested_currencies)
    if result.missing:
        slog_missing = sorted(result.missing)
        logger.debug("forex_queue_missing_currencies count=%d keys=%s", len(slog_missing), slog_missing[:20])

    normalized: list[NormalizedForex] = []
    for quote, (dto, source) in result.items.items():
        normalized.append(dto.model_copy(update={"provider_source": source}))
    normalized.sort(key=lambda item: item.symbol)
    return normalized


class ForexUnifiedAdapter(ForexProviderAdapter):
    """Unified forex adapter: configured source -> open.er fallback -> Frankfurter fallback."""

    provider_source = FOREX_PROVIDER_OPENEXCHANGERATES

    def __init__(
        self,
        timeout: float = DEFAULT_MARKET_DATA_TIMEOUT_SECONDS,
        retry_attempts: int = 0,
    ):
        self.timeout = timeout
        self._retry_attempts = retry_attempts

    async def fetch(self) -> list[NormalizedForex]:
        return await fetch_forex_normalized(
            base="EUR",
            timeout=self.timeout,
            retry_attempts=self._retry_attempts,
        )
