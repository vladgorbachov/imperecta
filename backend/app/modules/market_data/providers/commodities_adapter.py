"""Unified commodities provider (Gold API + Alpha Vantage + Yahoo gap-fill queue)."""

import logging
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

import httpx

from app.config import Settings
from app.modules.market_data.dto import NormalizedCommodity
from app.modules.market_data.http_config import (
    DEFAULT_MARKET_DATA_TIMEOUT_SECONDS,
    with_transient_retries,
)
from app.modules.market_data.provider_queue import gap_fill_fetch
from app.modules.market_data.providers.base import CommoditiesProviderAdapter

logger = logging.getLogger(__name__)

GOLD_API_DEFAULT_BASE_URL = "https://api.gold-api.com/price"
ALPHA_VANTAGE_QUERY_URL = "https://www.alphavantage.co/query"
YAHOO_CHART_BASE_URL = "https://query1.finance.yahoo.com/v8/finance/chart"

COMMODITY_PROVIDER_GOLDAPI = "goldapi"
COMMODITY_PROVIDER_ALPHA_VANTAGE = "alpha_vantage"
COMMODITY_PROVIDER_YAHOO = "yahoo"

METAL_ITEMS: tuple[tuple[str, str, str], ...] = (
    ("XAU", "Gold", "oz"),
    ("XAG", "Silver", "oz"),
    ("XPT", "Platinum", "oz"),
    ("XPD", "Palladium", "oz"),
)

METAL_YAHOO_SYMBOLS: dict[str, str] = {
    "XAU": "GC=F",
    "XAG": "SI=F",
    "XPT": "PL=F",
    "XPD": "PA=F",
}

ENERGY_ITEMS: tuple[tuple[str, str, str, str], ...] = (
    ("WTI", "Crude Oil (WTI)", "bbl", "CL=F"),
    ("BRENT", "Crude Oil (Brent)", "bbl", "BZ=F"),
)

METAL_SYMBOL_SET = frozenset(symbol for symbol, _, _ in METAL_ITEMS)
ENERGY_SYMBOL_SET = frozenset(symbol for symbol, _, _, _ in ENERGY_ITEMS)

_COMMODITY_CATALOG: dict[str, dict[str, str | None]] = {}
for _symbol, _name, _unit in METAL_ITEMS:
    _COMMODITY_CATALOG[_symbol] = {
        "name": _name,
        "unit": _unit,
        "yahoo_symbol": METAL_YAHOO_SYMBOLS.get(_symbol),
    }
for _symbol, _name, _unit, _yahoo in ENERGY_ITEMS:
    _COMMODITY_CATALOG[_symbol] = {
        "name": _name,
        "unit": _unit,
        "yahoo_symbol": _yahoo,
    }

_COMMODITY_PRICE_QUANT = Decimal("0.0001")


def commodity_catalog_symbols() -> frozenset[str]:
    """Fixed ingest/UI catalog: metals + energy symbols."""
    return METAL_SYMBOL_SET | ENERGY_SYMBOL_SET


def _quantize_commodity_price(price: Decimal) -> Decimal:
    """Round to 4 decimal places for fact_commodity_price Numeric(12,4)."""
    return price.quantize(_COMMODITY_PRICE_QUANT, rounding=ROUND_HALF_UP)


class _CommodityFetchEngine:
    """Shared HTTP fetch helpers for queue-backed commodity providers."""

    def __init__(
        self,
        *,
        base_url: str,
        gold_api_key: str,
        alpha_vantage_key: str,
        timeout: float,
        retry_attempts: int,
        refreshed_at: datetime,
    ) -> None:
        self.base_url = base_url
        self.gold_api_key = gold_api_key
        self.alpha_vantage_key = alpha_vantage_key
        self.timeout = timeout
        self._retry_attempts = retry_attempts
        self.refreshed_at = refreshed_at

    async def fetch_metal_from_gold_api(
        self,
        client: httpx.AsyncClient,
        *,
        symbol: str,
        name: str,
        unit: str,
    ) -> NormalizedCommodity | None:
        url = f"{self.base_url.rstrip('/')}/{symbol}"
        headers: dict[str, str] = {}
        if self.gold_api_key:
            headers["x-access-token"] = self.gold_api_key

        async def _request() -> NormalizedCommodity:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            payload = response.json()
            price_raw = payload.get("price", payload.get("close"))
            if price_raw is None:
                raise ValueError(f"Gold API payload missing price for {symbol}")
            price = _quantize_commodity_price(Decimal(str(price_raw)))
            change_raw = payload.get("chp", payload.get("change_24h"))
            change_24h = float(change_raw) if change_raw is not None else None
            return NormalizedCommodity(
                symbol=symbol,
                name=name,
                price=price,
                change_24h=change_24h,
                unit=unit,
                refreshed_at=self.refreshed_at,
                provider_source=COMMODITY_PROVIDER_GOLDAPI,
            )

        try:
            return await with_transient_retries(
                _request,
                retry_attempts=self._retry_attempts,
                label=f"GoldAPI:{symbol}",
            )
        except Exception as error:
            logger.warning("Gold API fetch failed for %s: %s", symbol, error)
            return None

    async def fetch_energy_from_alpha_vantage(
        self,
        client: httpx.AsyncClient,
        *,
        symbol: str,
        name: str,
        unit: str,
    ) -> NormalizedCommodity | None:
        if not self.alpha_vantage_key:
            return None

        async def _request() -> NormalizedCommodity | None:
            response = await client.get(
                ALPHA_VANTAGE_QUERY_URL,
                params={
                    "function": symbol,
                    "interval": "daily",
                    "apikey": self.alpha_vantage_key,
                },
            )
            response.raise_for_status()
            payload = response.json()
            if payload.get("Error Message") or payload.get("Note"):
                return None
            rows = payload.get("data")
            if not isinstance(rows, list) or len(rows) < 2:
                return None
            latest = _quantize_commodity_price(Decimal(str(rows[0].get("value"))))
            previous = Decimal(str(rows[1].get("value")))
            change_24h = None
            if previous != 0:
                change_24h = float(((latest - previous) / previous) * 100)
            return NormalizedCommodity(
                symbol=symbol,
                name=name,
                price=latest,
                change_24h=change_24h,
                unit=unit,
                refreshed_at=self.refreshed_at,
                provider_source=COMMODITY_PROVIDER_ALPHA_VANTAGE,
            )

        try:
            return await with_transient_retries(
                _request,
                retry_attempts=self._retry_attempts,
                label=f"AlphaVantage:{symbol}",
            )
        except Exception:
            return None

    async def fetch_from_yahoo_chart(
        self,
        client: httpx.AsyncClient,
        *,
        symbol: str,
        name: str,
        unit: str,
        yahoo_symbol: str,
    ) -> NormalizedCommodity | None:
        async def _request() -> NormalizedCommodity:
            response = await client.get(
                f"{YAHOO_CHART_BASE_URL.rstrip('/')}/{yahoo_symbol}",
                params={"interval": "1d", "range": "5d"},
            )
            response.raise_for_status()
            payload = response.json()
            result = (((payload.get("chart") or {}).get("result") or [None])[0] or {})
            meta = result.get("meta") or {}
            latest_raw = meta.get("regularMarketPrice", meta.get("previousClose"))
            if latest_raw is None:
                raise ValueError(f"Yahoo chart missing price for {yahoo_symbol}")
            previous_raw = meta.get("previousClose")
            latest = _quantize_commodity_price(Decimal(str(latest_raw)))
            previous = (
                _quantize_commodity_price(Decimal(str(previous_raw)))
                if previous_raw is not None
                else None
            )
            change_24h = None
            if previous is not None and previous != 0:
                change_24h = float(((latest - previous) / previous) * 100)
            return NormalizedCommodity(
                symbol=symbol,
                name=name,
                price=latest,
                change_24h=change_24h,
                unit=unit,
                refreshed_at=self.refreshed_at,
                provider_source=COMMODITY_PROVIDER_YAHOO,
            )

        try:
            return await with_transient_retries(
                _request,
                retry_attempts=self._retry_attempts,
                label=f"Yahoo:{yahoo_symbol}",
            )
        except Exception as error:
            logger.warning(
                "Yahoo fallback failed for %s (%s): %s",
                symbol,
                yahoo_symbol,
                error,
            )
            return None


class _QueuedGoldApiProvider:
    """Gold API queue provider for catalog metals."""

    def __init__(self, engine: _CommodityFetchEngine) -> None:
        self._engine = engine

    @property
    def provider_source(self) -> str:
        return COMMODITY_PROVIDER_GOLDAPI

    async def fetch_instruments(self, requested: frozenset[str]) -> dict[str, NormalizedCommodity]:
        targets = requested & METAL_SYMBOL_SET
        if not targets:
            return {}
        out: dict[str, NormalizedCommodity] = {}
        async with httpx.AsyncClient(timeout=self._engine.timeout) as client:
            for symbol in sorted(targets):
                meta = _COMMODITY_CATALOG[symbol]
                item = await self._engine.fetch_metal_from_gold_api(
                    client,
                    symbol=symbol,
                    name=str(meta["name"]),
                    unit=str(meta["unit"]),
                )
                if item is not None:
                    out[symbol] = item
        return out


class _QueuedAlphaVantageProvider:
    """Alpha Vantage queue provider for catalog energy symbols."""

    def __init__(self, engine: _CommodityFetchEngine) -> None:
        self._engine = engine

    @property
    def provider_source(self) -> str:
        return COMMODITY_PROVIDER_ALPHA_VANTAGE

    async def fetch_instruments(self, requested: frozenset[str]) -> dict[str, NormalizedCommodity]:
        targets = requested & ENERGY_SYMBOL_SET
        if not targets:
            return {}
        out: dict[str, NormalizedCommodity] = {}
        async with httpx.AsyncClient(timeout=self._engine.timeout) as client:
            for symbol in sorted(targets):
                meta = _COMMODITY_CATALOG[symbol]
                item = await self._engine.fetch_energy_from_alpha_vantage(
                    client,
                    symbol=symbol,
                    name=str(meta["name"]),
                    unit=str(meta["unit"]),
                )
                if item is not None:
                    out[symbol] = item
        return out


class _QueuedYahooProvider:
    """Yahoo chart queue provider for catalog symbols with futures tickers."""

    def __init__(self, engine: _CommodityFetchEngine) -> None:
        self._engine = engine

    @property
    def provider_source(self) -> str:
        return COMMODITY_PROVIDER_YAHOO

    async def fetch_instruments(self, requested: frozenset[str]) -> dict[str, NormalizedCommodity]:
        out: dict[str, NormalizedCommodity] = {}
        async with httpx.AsyncClient(timeout=self._engine.timeout) as client:
            for symbol in sorted(requested):
                meta = _COMMODITY_CATALOG.get(symbol)
                yahoo_symbol = meta.get("yahoo_symbol") if meta else None
                if not yahoo_symbol:
                    continue
                item = await self._engine.fetch_from_yahoo_chart(
                    client,
                    symbol=symbol,
                    name=str(meta["name"]),
                    unit=str(meta["unit"]),
                    yahoo_symbol=str(yahoo_symbol),
                )
                if item is not None:
                    out[symbol] = item
        return out


def build_commodities_queue_providers(
    *,
    engine: _CommodityFetchEngine,
) -> list[_QueuedGoldApiProvider | _QueuedAlphaVantageProvider | _QueuedYahooProvider]:
    """Queue order: Gold API metals, Alpha Vantage energy, Yahoo gap-fill."""
    return [
        _QueuedGoldApiProvider(engine),
        _QueuedAlphaVantageProvider(engine),
        _QueuedYahooProvider(engine),
    ]


def _build_fetch_engine(
    *,
    base_url: str | None,
    timeout: float,
    retry_attempts: int,
    refreshed_at: datetime,
) -> _CommodityFetchEngine:
    settings = Settings()
    configured_base = (base_url or settings.market_data_commodities_url or "").strip()
    return _CommodityFetchEngine(
        base_url=configured_base or GOLD_API_DEFAULT_BASE_URL,
        gold_api_key=(settings.goldapi_key or "").strip(),
        alpha_vantage_key=(settings.alpha_vantage_key or "").strip(),
        timeout=timeout,
        retry_attempts=retry_attempts,
        refreshed_at=refreshed_at,
    )


async def fetch_commodities_normalized(
    *,
    base_url: str | None = None,
    timeout: float = DEFAULT_MARKET_DATA_TIMEOUT_SECONDS,
    retry_attempts: int = 0,
    requested_symbols: frozenset[str] | None = None,
) -> list[NormalizedCommodity]:
    """Fetch commodities via cross-provider gap-fill over the fixed catalog."""
    refreshed_at = datetime.now(timezone.utc)
    engine = _build_fetch_engine(
        base_url=base_url,
        timeout=timeout,
        retry_attempts=retry_attempts,
        refreshed_at=refreshed_at,
    )
    if requested_symbols is None:
        requested_symbols = commodity_catalog_symbols()

    providers = build_commodities_queue_providers(engine=engine)
    result = await gap_fill_fetch(providers, requested_symbols)
    if result.missing:
        missing = sorted(result.missing)
        logger.debug(
            "commodities_queue_missing_symbols count=%d keys=%s",
            len(missing),
            missing,
        )

    normalized: list[NormalizedCommodity] = []
    for symbol, (dto, source) in result.items.items():
        normalized.append(dto.model_copy(update={"provider_source": source}))
    normalized.sort(key=lambda item: item.symbol)
    logger.info("Commodities queue fetched %d items", len(normalized))
    return normalized


class CommoditiesUnifiedAdapter(CommoditiesProviderAdapter):
    """
    Unified commodities adapter aligned with Chrome extension data flow:
    - metals: Gold API, Yahoo gap-fill
    - energy: Alpha Vantage, Yahoo gap-fill
    """

    def __init__(
        self,
        base_url: str | None = None,
        timeout: float = DEFAULT_MARKET_DATA_TIMEOUT_SECONDS,
        retry_attempts: int = 0,
    ):
        self.base_url = base_url
        self.timeout = timeout
        self._retry_attempts = retry_attempts

    async def fetch(self) -> list[NormalizedCommodity]:
        return await fetch_commodities_normalized(
            base_url=self.base_url,
            timeout=self.timeout,
            retry_attempts=self._retry_attempts,
        )
