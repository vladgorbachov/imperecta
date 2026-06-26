"""Crypto providers: Binance primary, CoinGecko backup. Top 50 by volume / market cap."""

import logging
from datetime import datetime, timezone
from decimal import Decimal

import httpx

from app.config import Settings
from app.modules.market_data.dto import NormalizedCrypto
from app.modules.market_data.http_config import (
    DEFAULT_MARKET_DATA_TIMEOUT_SECONDS,
    with_transient_retries,
)
from app.modules.market_data.provider_queue import gap_fill_fetch
from app.modules.market_data.providers.base import CryptoProviderAdapter
from app.modules.market_data.providers.binance_adapter import TOP_N, BinanceCryptoAdapter

logger = logging.getLogger(__name__)
COINGECKO_FALLBACK_URL = "https://api.coingecko.com/api/v3/coins/markets"

CRYPTO_PROVIDER_BINANCE = "binance"
CRYPTO_PROVIDER_COINGECKO = "coingecko"


class CryptoCoingeckoAdapter(CryptoProviderAdapter):
    """CoinGecko markets adapter (backup). Normalizes to NormalizedCrypto."""

    provider_source = CRYPTO_PROVIDER_COINGECKO

    def __init__(
        self,
        base_url: str | None = None,
        timeout: float = DEFAULT_MARKET_DATA_TIMEOUT_SECONDS,
        per_page: int = TOP_N,
    ):
        self.base_url = base_url or COINGECKO_FALLBACK_URL
        self.timeout = timeout
        self.per_page = per_page

    async def fetch(self) -> list[NormalizedCrypto]:
        """Fetch top coins from CoinGecko. Returns normalized list."""
        refreshed_at = datetime.now(timezone.utc)
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(
                self.base_url,
                params={
                    "vs_currency": "usd",
                    "order": "market_cap_desc",
                    "per_page": self.per_page,
                    "page": 1,
                    "sparkline": "false",
                    "price_change_percentage": "24h",
                },
            )
            resp.raise_for_status()
            data = resp.json()

        if not isinstance(data, list):
            logger.warning("CoinGecko response not a list: %s", type(data))
            return []

        items: list[NormalizedCrypto] = []
        for row in data:
            try:
                symbol = str(row.get("symbol", "")).upper()
                price = Decimal(str(row.get("current_price", 0)))
                change = row.get("price_change_percentage_24h")
                change_24h = float(change) if change is not None else None
                market_cap_raw = row.get("market_cap")
                market_cap = Decimal(str(market_cap_raw)) if market_cap_raw is not None else None
                items.append(
                    NormalizedCrypto(
                        symbol=symbol,
                        price=price,
                        change_24h=change_24h,
                        market_cap=market_cap,
                        refreshed_at=refreshed_at,
                        provider_source=self.provider_source,
                    )
                )
            except Exception as error:
                logger.warning("Parse crypto row %s: %s", row.get("id"), error)
                continue

        logger.info("Crypto CoinGecko adapter fetched %d assets", len(items))
        return items


class CryptoCompositeAdapter(CryptoProviderAdapter):
    """Legacy Binance-primary composite kept for callers that bypass the queue."""

    def __init__(
        self,
        timeout: float = DEFAULT_MARKET_DATA_TIMEOUT_SECONDS,
        retry_attempts: int = 0,
    ):
        self.timeout = timeout
        self._retry_attempts = retry_attempts
        self._binance = BinanceCryptoAdapter(timeout=timeout)
        self._coingecko = CryptoCoingeckoAdapter(timeout=timeout, per_page=TOP_N)

    async def fetch(self) -> list[NormalizedCrypto]:
        """Fetch crypto via the queue-backed normalized path."""
        return await fetch_crypto_normalized(
            timeout=self.timeout,
            retry_attempts=self._retry_attempts,
        )


class _QueuedCryptoProvider:
    """Wraps a ranked-batch crypto adapter for gap-fill queue (keyed by symbol)."""

    def __init__(
        self,
        adapter: CryptoProviderAdapter,
        *,
        provider_source: str,
        retry_attempts: int,
    ) -> None:
        self._adapter = adapter
        self._provider_source = provider_source
        self._retry_attempts = retry_attempts

    @property
    def provider_source(self) -> str:
        return self._provider_source

    async def fetch_instruments(self, requested: frozenset[str]) -> dict[str, NormalizedCrypto]:
        """Return ranked batch (discovery) or intersection with ``requested``."""
        items = await with_transient_retries(
            self._adapter.fetch,
            retry_attempts=self._retry_attempts,
            label=self._adapter.__class__.__name__,
        )
        out: dict[str, NormalizedCrypto] = {}
        for dto in items:
            symbol = dto.symbol.strip().upper()
            if not symbol:
                continue
            if requested and symbol not in requested:
                continue
            out[symbol] = dto.model_copy(update={"provider_source": self._provider_source})
        return out


def build_crypto_queue_providers(
    *,
    timeout: float,
    retry_attempts: int,
) -> list[_QueuedCryptoProvider]:
    """Build crypto queue: Binance first (universe definer), CoinGecko gap-fill second.

    A configured ``market_data_crypto_url`` overrides the CoinGecko endpoint only when
    it is not a Binance URL; it never precedes Binance in the queue.
    """
    configured = (Settings().market_data_crypto_url or "").strip()
    binance_base: str | None = None
    coingecko_base: str | None = None
    if configured:
        if "binance" in configured.lower():
            binance_base = configured
        else:
            coingecko_base = configured

    return [
        _QueuedCryptoProvider(
            BinanceCryptoAdapter(base_url=binance_base, timeout=timeout),
            provider_source=CRYPTO_PROVIDER_BINANCE,
            retry_attempts=retry_attempts,
        ),
        _QueuedCryptoProvider(
            CryptoCoingeckoAdapter(
                base_url=coingecko_base,
                timeout=timeout,
                per_page=TOP_N,
            ),
            provider_source=CRYPTO_PROVIDER_COINGECKO,
            retry_attempts=retry_attempts,
        ),
    ]


async def _discover_crypto_requested(
    providers: list[_QueuedCryptoProvider],
) -> frozenset[str]:
    """Derive target symbols from the first provider that returns a ranked batch."""
    for provider in providers:
        batch = await provider.fetch_instruments(frozenset())
        if batch:
            return frozenset(batch.keys())
    return frozenset()


async def fetch_crypto_normalized(
    *,
    timeout: float = DEFAULT_MARKET_DATA_TIMEOUT_SECONDS,
    retry_attempts: int = 0,
    requested_symbols: frozenset[str] | None = None,
) -> list[NormalizedCrypto]:
    """Fetch crypto via cross-provider gap-fill queue.

    Ranked providers (Binance TOP_N by volume, CoinGecko per_page=TOP_N by market cap)
    do not use a fixed symbol manifest. When ``requested_symbols`` is omitted, the
    requested key set is discovered from the first successful provider's ranked batch;
    ``gap_fill_fetch`` then gap-fills missing keys within that universe.
    """
    providers = build_crypto_queue_providers(
        timeout=timeout,
        retry_attempts=retry_attempts,
    )
    if requested_symbols is None:
        requested_symbols = await _discover_crypto_requested(providers)
    if not requested_symbols:
        return []

    result = await gap_fill_fetch(providers, requested_symbols)
    if result.missing:
        missing = sorted(result.missing)
        logger.debug(
            "crypto_queue_missing_symbols count=%d keys=%s",
            len(missing),
            missing[:20],
        )

    normalized: list[NormalizedCrypto] = []
    for symbol, (dto, source) in result.items.items():
        normalized.append(dto.model_copy(update={"provider_source": source}))
    normalized.sort(key=lambda item: item.symbol)
    return normalized


class CryptoUnifiedAdapter(CryptoProviderAdapter):
    """Unified crypto adapter: Binance primary + CoinGecko gap-fill via queue."""

    provider_source = CRYPTO_PROVIDER_BINANCE

    def __init__(
        self,
        timeout: float = DEFAULT_MARKET_DATA_TIMEOUT_SECONDS,
        retry_attempts: int = 0,
    ):
        self.timeout = timeout
        self._retry_attempts = retry_attempts

    async def fetch(self) -> list[NormalizedCrypto]:
        return await fetch_crypto_normalized(
            timeout=self.timeout,
            retry_attempts=self._retry_attempts,
        )
