"""
Market data ingestion orchestration. Fetches from providers, validates, persists.
Isolated from legacy dashboard/anomalies. No routing through benchmark or anomalies.
"""

import asyncio
import logging
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models import (
    MarketsCommodity,
    MarketsCrypto,
    MarketsForex,
    MarketsRefreshLog,
    MarketsRefreshStatus,
    MarketsRefreshType,
)
from app.services.market_data.providers.fuel_adapter import FuelHttpAdapter
from app.services.market_data.dto import (
    NormalizedCommodity,
    NormalizedCrypto,
    NormalizedForex,
)
from app.services.market_data.providers.commodities_adapter import (
    CommoditiesHttpAdapter,
)
from app.services.market_data.providers.commodities_goldapi_alphavantage import (
    CommoditiesGoldAPIAlphaVantageAdapter,
)
from app.services.market_data.providers.crypto_adapter import CryptoCoingeckoAdapter
from app.services.market_data.providers.forex_adapter import ForexFrankfurterAdapter

logger = logging.getLogger(__name__)
settings = Settings()

PROVIDER_FOREX = "frankfurter"
PROVIDER_CRYPTO = "coingecko"
PROVIDER_COMMODITIES = "http"
PROVIDER_FUEL = "fuel"


def _provider_for_type(refresh_type: MarketsRefreshType) -> str:
    if refresh_type == MarketsRefreshType.forex:
        return PROVIDER_FOREX
    if refresh_type == MarketsRefreshType.crypto:
        return PROVIDER_CRYPTO
    if refresh_type == MarketsRefreshType.commodities:
        return PROVIDER_COMMODITIES
    if refresh_type == MarketsRefreshType.fuel:
        return PROVIDER_FUEL
    return "unknown"


class MarketDataIngestionService:
    """
    Orchestrates market data fetch, validation, and persistence.
    Uses retry/timeout. Provider-specific shapes never leave adapters.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.timeout = settings.market_data_timeout_seconds
        self.retry_attempts = settings.market_data_retry_attempts

    async def _fetch_with_retry(self, fetch_fn, refresh_type: MarketsRefreshType):
        """Execute fetch with retries and log to refresh_log."""
        log_entry = MarketsRefreshLog(
            refresh_type=refresh_type,
            status=MarketsRefreshStatus.running,
            provider_source=_provider_for_type(refresh_type),
        )
        self.db.add(log_entry)
        await self.db.flush()

        last_error: Exception | None = None
        for attempt in range(1, self.retry_attempts + 1):
            try:
                result = await asyncio.wait_for(
                    fetch_fn(),
                    timeout=float(self.timeout),
                )
                log_entry.status = MarketsRefreshStatus.success
                log_entry.completed_at = datetime.now(timezone.utc)
                log_entry.error_message = None
                await self.db.flush()
                return result
            except asyncio.TimeoutError as e:
                last_error = e
                logger.warning(
                    "Market data %s attempt %d timeout",
                    refresh_type.value,
                    attempt,
                )
            except Exception as e:
                last_error = e
                logger.warning(
                    "Market data %s attempt %d error: %s",
                    refresh_type.value,
                    attempt,
                    e,
                    exc_info=True,
                )
            if attempt < self.retry_attempts:
                await asyncio.sleep(2**attempt)

        log_entry.status = MarketsRefreshStatus.error
        log_entry.completed_at = datetime.now(timezone.utc)
        log_entry.error_message = str(last_error) if last_error else "Unknown error"
        await self.db.flush()
        raise last_error or RuntimeError("Ingestion failed")

    async def ingest_forex(self) -> int:
        """Fetch forex from provider, validate, persist. Returns count persisted."""
        adapter = ForexFrankfurterAdapter(timeout=float(self.timeout))
        items = await self._fetch_with_retry(
            adapter.fetch,
            MarketsRefreshType.forex,
        )
        if not items:
            return 0

        for dto in items:
            stmt = insert(MarketsForex).values(
                symbol=dto.symbol,
                bid=dto.bid,
                ask=dto.ask,
                spread=dto.spread,
                change_24h=Decimal(str(dto.change_24h)) if dto.change_24h is not None else None,
                refreshed_at=dto.refreshed_at,
            ).on_conflict_do_update(
                index_elements=["symbol"],
                set_={
                    "bid": dto.bid,
                    "ask": dto.ask,
                    "spread": dto.spread,
                    "change_24h": Decimal(str(dto.change_24h)) if dto.change_24h is not None else None,
                    "refreshed_at": dto.refreshed_at,
                },
            )
            await self.db.execute(stmt)

        await self.db.flush()
        logger.info("Persisted %d forex pairs", len(items))
        return len(items)

    async def ingest_crypto(self) -> int:
        """Fetch crypto from provider, validate, persist. Returns count persisted."""
        adapter = CryptoCoingeckoAdapter(timeout=float(self.timeout))
        items = await self._fetch_with_retry(
            adapter.fetch,
            MarketsRefreshType.crypto,
        )
        if not items:
            return 0

        for dto in items:
            stmt = insert(MarketsCrypto).values(
                symbol=dto.symbol,
                price=dto.price,
                change_24h=Decimal(str(dto.change_24h)) if dto.change_24h is not None else None,
                market_cap=Decimal(str(dto.market_cap)) if dto.market_cap is not None else None,
                refreshed_at=dto.refreshed_at,
            ).on_conflict_do_update(
                index_elements=["symbol"],
                set_={
                    "price": dto.price,
                    "change_24h": Decimal(str(dto.change_24h)) if dto.change_24h is not None else None,
                    "market_cap": Decimal(str(dto.market_cap)) if dto.market_cap is not None else None,
                    "refreshed_at": dto.refreshed_at,
                },
            )
            await self.db.execute(stmt)

        await self.db.flush()
        logger.info("Persisted %d crypto assets", len(items))
        return len(items)

    async def ingest_commodities(self) -> int:
        """Fetch commodities from GoldAPI + Alpha Vantage, validate, persist. Returns count persisted."""
        # Prefer real APIs (GoldAPI + Alpha Vantage) over legacy HTTP URL
        if settings.goldapi_key or settings.alpha_vantage_key:
            adapter = CommoditiesGoldAPIAlphaVantageAdapter()
        elif settings.market_data_commodities_url.strip():
            adapter = CommoditiesHttpAdapter(timeout=float(self.timeout))
        else:
            logger.debug("Commodities: no GOLDAPI_KEY, ALPHA_VANTAGE_KEY, or MARKET_DATA_COMMODITIES_URL")
            return 0

        items = await self._fetch_with_retry(
            adapter.fetch,
            MarketsRefreshType.commodities,
        )
        if not items:
            return 0

        for dto in items:
            stmt = insert(MarketsCommodity).values(
                symbol=dto.symbol,
                name=dto.name,
                price=dto.price,
                change_24h=Decimal(str(dto.change_24h)) if dto.change_24h is not None else None,
                unit=dto.unit,
                refreshed_at=dto.refreshed_at,
            ).on_conflict_do_update(
                index_elements=["symbol"],
                set_={
                    "name": dto.name,
                    "price": dto.price,
                    "change_24h": Decimal(str(dto.change_24h)) if dto.change_24h is not None else None,
                    "unit": dto.unit,
                    "refreshed_at": dto.refreshed_at,
                },
            )
            await self.db.execute(stmt)

        await self.db.flush()
        logger.info("Persisted %d commodities", len(items))
        return len(items)

    async def ingest_fuel(self) -> int:
        """Fetch fuel/internal data. Persist to markets_commodities. Returns count."""
        if not settings.market_data_fuel_url.strip():
            logger.debug("Fuel URL not configured, skipping")
            return 0

        adapter = FuelHttpAdapter(timeout=float(self.timeout))
        items = await self._fetch_with_retry(
            adapter.fetch,
            MarketsRefreshType.fuel,
        )
        if not items:
            return 0

        for dto in items:
            stmt = insert(MarketsCommodity).values(
                symbol=dto.symbol,
                name=dto.name,
                price=dto.price,
                change_24h=Decimal(str(dto.change_24h)) if dto.change_24h is not None else None,
                unit=dto.unit,
                refreshed_at=dto.refreshed_at,
            ).on_conflict_do_update(
                index_elements=["symbol"],
                set_={
                    "name": dto.name,
                    "price": dto.price,
                    "change_24h": Decimal(str(dto.change_24h)) if dto.change_24h is not None else None,
                    "unit": dto.unit,
                    "refreshed_at": dto.refreshed_at,
                },
            )
            await self.db.execute(stmt)

        await self.db.flush()
        logger.info("Persisted %d fuel items", len(items))
        return len(items)

    async def ingest_all(self) -> dict[str, int]:
        """Run all ingestion pipelines. Returns counts per type."""
        results: dict[str, int] = {}
        for name, fn in [
            ("forex", self.ingest_forex),
            ("crypto", self.ingest_crypto),
            ("commodities", self.ingest_commodities),
            ("fuel", self.ingest_fuel),
        ]:
            try:
                count = await fn()
                results[name] = count
            except Exception as e:
                logger.error("Ingestion %s failed: %s", name, e, exc_info=True)
                results[name] = 0
        return results
