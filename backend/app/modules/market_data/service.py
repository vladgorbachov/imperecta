"""
Real market data service and markets domain service.
Fetches forex, crypto, commodities, and fuel prices from APIs.
"""

import asyncio
import logging
import time
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Iterable

import httpx
from sqlalchemy import asc, func, nullslast, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models.app_tables import ApiLog
from app.models.core import User
from app.models.facts import (
    FactCommodityPrice,
    FactCryptoPrice,
    FactCurrencyRate,
    FactFuelPrice,
)

logger = logging.getLogger(__name__)

_V2_MSG = "Pending migration to v2 schema"


class MarketDataService:
    """Read forex, crypto, commodities, and fuel from v2 fact tables."""

    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def _dedupe_currency_rows(rows: list[FactCurrencyRate]) -> list[FactCurrencyRate]:
        """Keep one row per currency (first after ordering by currency_code, source)."""
        seen: set[str] = set()
        out: list[FactCurrencyRate] = []
        for r in rows:
            if r.currency_code in seen:
                continue
            seen.add(r.currency_code)
            out.append(r)
        return out

    @staticmethod
    def _dedupe_crypto_rows(rows: list[FactCryptoPrice]) -> list[FactCryptoPrice]:
        """Keep one row per symbol (prefer lower rank)."""
        best: dict[str, FactCryptoPrice] = {}
        for r in rows:
            cur = best.get(r.symbol)
            if cur is None:
                best[r.symbol] = r
                continue
            cr = cur.rank if cur.rank is not None else 9999
            rr = r.rank if r.rank is not None else 9999
            if rr < cr:
                best[r.symbol] = r
        return list(best.values())

    @staticmethod
    def _dedupe_commodity_rows(rows: list[FactCommodityPrice]) -> list[FactCommodityPrice]:
        """Keep one row per symbol (first wins)."""
        seen: set[str] = set()
        out: list[FactCommodityPrice] = []
        for r in rows:
            if r.symbol in seen:
                continue
            seen.add(r.symbol)
            out.append(r)
        return out

    async def get_forex(self) -> list[dict[str, Any]]:
        """Latest forex rates from fact_currency_rate."""
        latest_date = await self.db.scalar(select(func.max(FactCurrencyRate.date_id)))
        if not latest_date:
            return []
        result = await self.db.execute(
            select(FactCurrencyRate)
            .where(FactCurrencyRate.date_id == latest_date)
            .order_by(FactCurrencyRate.currency_code, FactCurrencyRate.source),
        )
        rows = self._dedupe_currency_rows(list(result.scalars().all()))
        return [
            {
                "currency_code": r.currency_code,
                "rate_to_eur": float(r.rate_to_eur),
                "rate_to_usd": float(r.rate_to_usd),
                "source": r.source,
                "fetched_at": r.fetched_at.isoformat() if r.fetched_at else None,
            }
            for r in rows
        ]

    async def get_crypto(self) -> list[dict[str, Any]]:
        """Latest crypto prices from fact_crypto_price."""
        latest_date = await self.db.scalar(select(func.max(FactCryptoPrice.date_id)))
        if not latest_date:
            return []
        result = await self.db.execute(
            select(FactCryptoPrice)
            .where(FactCryptoPrice.date_id == latest_date)
            .order_by(nullslast(asc(FactCryptoPrice.rank)), FactCryptoPrice.symbol),
        )
        rows = self._dedupe_crypto_rows(list(result.scalars().all()))
        return [self._crypto_to_dict(r) for r in rows]

    async def get_commodities(self) -> list[dict[str, Any]]:
        """Latest commodity prices from fact_commodity_price."""
        latest_date = await self.db.scalar(select(func.max(FactCommodityPrice.date_id)))
        if not latest_date:
            return []
        result = await self.db.execute(
            select(FactCommodityPrice)
            .where(FactCommodityPrice.date_id == latest_date)
            .order_by(FactCommodityPrice.symbol, FactCommodityPrice.source),
        )
        rows = self._dedupe_commodity_rows(list(result.scalars().all()))
        return [self._commodity_to_dict(r) for r in rows]

    async def get_fuel(self, country_code: str) -> list[dict[str, Any]]:
        """Latest fuel prices for country from fact_fuel_price."""
        code = country_code.upper()
        latest_date = await self.db.scalar(
            select(func.max(FactFuelPrice.date_id)).where(FactFuelPrice.country_code == code),
        )
        if not latest_date:
            return []
        result = await self.db.execute(
            select(FactFuelPrice)
            .where(FactFuelPrice.date_id == latest_date)
            .where(FactFuelPrice.country_code == code)
            .order_by(FactFuelPrice.fuel_type),
        )
        return [self._fuel_to_dict(r) for r in result.scalars().all()]

    async def get_preferences(self, user: User) -> dict[str, Any]:
        """User preferences from users.preferences JSONB."""
        prefs = user.preferences or {}
        return {
            "dashboard_widgets": prefs.get(
                "dashboard_widgets",
                ["forex", "crypto", "commodities", "fuel"],
            ),
            "forex_favorites": prefs.get("forex_favorites", []),
            "crypto_favorites": prefs.get("crypto_favorites", []),
            "commodity_favorites": prefs.get("commodity_favorites", []),
            "favorite_instrument_ids": prefs.get("favorite_instrument_ids", []),
        }

    async def update_preferences(self, user: User, updates: dict[str, Any]) -> dict[str, Any]:
        """Merge updates into users.preferences JSONB."""
        prefs = dict(user.preferences or {})
        for k, v in updates.items():
            if v is not None:
                prefs[k] = v
        user.preferences = prefs
        await self.db.commit()
        await self.db.refresh(user)
        return await self.get_preferences(user)

    async def get_ticker(
        self,
        country_code: str,
        forex_favorites: Iterable[str] | None = None,
        crypto_favorites: Iterable[str] | None = None,
        commodity_favorites: Iterable[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Build ticker from latest forex + crypto + commodities (+ fuel from DB when available)."""
        forex_set = {value.strip().upper() for value in (forex_favorites or []) if value}
        crypto_set = {value.strip().upper() for value in (crypto_favorites or []) if value}
        commodity_set = {value.strip().upper() for value in (commodity_favorites or []) if value}

        items: list[dict[str, Any]] = []
        for fx in await self.get_forex():
            cc = fx["currency_code"]
            if cc == "EUR":
                continue
            symbol = f"EUR/{cc}"
            if forex_set and symbol.upper() not in forex_set:
                continue
            rte = fx["rate_to_eur"]
            if rte and rte > 0:
                display = 1.0 / rte
            else:
                display = rte
            items.append({
                "symbol": symbol,
                "name": cc,
                "price": display,
                "change_pct": None,
                "type": "forex",
            })
        for c in (await self.get_crypto())[:5]:
            symbol = str(c["symbol"]).upper()
            if crypto_set and symbol not in crypto_set:
                continue
            items.append({
                "symbol": symbol,
                "name": c.get("name", c["symbol"]),
                "price": c["price_usd"],
                "change_pct": c.get("change_24h_pct"),
                "type": "crypto",
            })
        for cm in await self.get_commodities():
            symbol = str(cm["symbol"]).upper()
            if commodity_set and symbol not in commodity_set:
                continue
            items.append({
                "symbol": symbol,
                "name": cm["name"],
                "price": cm["price_usd"],
                "change_pct": cm.get("change_24h_pct"),
                "type": "commodity",
                "unit": cm.get("unit", ""),
            })
        fuel_rows = await self.get_fuel(country_code.upper())
        for row in fuel_rows:
            items.append({
                "symbol": f"{row['fuel_type']}@{country_code.upper()}",
                "name": row["fuel_type"],
                "price": row["price_local"],
                "change_pct": row.get("change_week_pct"),
                "type": "fuel",
                "currency_code": row["currency_code"],
            })
        return items

    async def get_available_forex_instruments(self) -> list[dict[str, Any]]:
        """Return forex symbols available in DB for instrument selection UI."""
        rows = await self.get_forex()
        options: list[dict[str, Any]] = []
        for idx, row in enumerate(rows):
            code = row.get("currency_code")
            if not code or code == "EUR":
                continue
            options.append({
                "symbol": f"EUR/{code}",
                "name": str(code),
                "rank": idx + 1,
                "category": "forex",
                "market_cap_usd": None,
            })
        options.sort(key=lambda item: item["symbol"])
        return options

    async def get_available_crypto_instruments(self) -> list[dict[str, Any]]:
        """Return crypto symbols available in DB for instrument selection UI."""
        rows = await self.get_crypto()
        options: list[dict[str, Any]] = [
            {
                "symbol": str(row["symbol"]).upper(),
                "name": row.get("name") or str(row["symbol"]).upper(),
                "rank": row.get("rank"),
                "category": "crypto",
                "market_cap_usd": row.get("market_cap_usd"),
            }
            for row in rows
            if row.get("symbol")
        ]
        options.sort(
            key=lambda item: (
                item["rank"] if isinstance(item["rank"], int) else 999999,
                -(float(item["market_cap_usd"]) if item["market_cap_usd"] is not None else 0.0),
                item["symbol"],
            )
        )
        return options

    async def get_available_commodity_instruments(self) -> list[dict[str, Any]]:
        """Return commodity symbols available in DB for instrument selection UI."""
        rows = await self.get_commodities()
        options: list[dict[str, Any]] = [
            {
                "symbol": str(row["symbol"]).upper(),
                "name": row.get("name") or str(row["symbol"]).upper(),
                "rank": None,
                "category": row.get("commodity_type"),
                "market_cap_usd": None,
            }
            for row in rows
            if row.get("symbol")
        ]
        options.sort(key=lambda item: item["symbol"])
        return options

    async def get_refresh_metadata(self) -> list[dict[str, Any]]:
        """Latest api_logs rows for market_data service (refresh audit)."""
        result = await self.db.execute(
            select(ApiLog)
            .where(ApiLog.service == "market_data")
            .order_by(ApiLog.created_at.desc())
            .limit(50),
        )
        rows = list(result.scalars().all())
        out: list[dict[str, Any]] = []
        for log in rows:
            ep = (log.endpoint or "").strip() or "unknown"
            refresh_type = ep.split("/")[0] if ep else "market_data"
            out.append({
                "refresh_type": refresh_type,
                "last_successful_refresh": log.created_at if log.status == "success" else None,
                "last_failed_refresh": log.created_at if log.status != "success" else None,
                "provider_source": ep,
                "country_scope": None,
                "error_message": log.error_message if log.status != "success" else None,
            })
        return out

    def _crypto_to_dict(self, r: FactCryptoPrice) -> dict[str, Any]:
        return {
            "symbol": r.symbol,
            "name": r.name,
            "price_usd": float(r.price_usd),
            "price_eur": float(r.price_eur) if r.price_eur is not None else None,
            "market_cap_usd": float(r.market_cap_usd) if r.market_cap_usd is not None else None,
            "volume_24h_usd": float(r.volume_24h_usd) if r.volume_24h_usd is not None else None,
            "change_24h_pct": float(r.change_24h_pct) if r.change_24h_pct is not None else None,
            "change_7d_pct": float(r.change_7d_pct) if r.change_7d_pct is not None else None,
            "rank": r.rank,
            "source": r.source,
            "fetched_at": r.fetched_at,
        }

    def _commodity_to_dict(self, r: FactCommodityPrice) -> dict[str, Any]:
        return {
            "symbol": r.symbol,
            "name": r.name,
            "commodity_type": r.commodity_type,
            "price_usd": float(r.price_usd),
            "price_eur": float(r.price_eur) if r.price_eur is not None else None,
            "change_24h_pct": float(r.change_24h_pct) if r.change_24h_pct is not None else None,
            "unit": r.unit,
            "source": r.source,
            "fetched_at": r.fetched_at,
        }

    def _fuel_to_dict(self, r: FactFuelPrice) -> dict[str, Any]:
        return {
            "fuel_type": r.fuel_type,
            "price_local": float(r.price_local),
            "currency_code": r.currency_code,
            "price_eur": float(r.price_eur) if r.price_eur is not None else None,
            "change_week_pct": float(r.change_week_pct) if r.change_week_pct is not None else None,
            "source": r.source,
            "fetched_at": r.fetched_at,
        }

    async def build_forex_api_response_async(self) -> tuple[list[dict[str, Any]], datetime | None]:
        """Build MarketsForexResponse-compatible item dicts from DB facts."""
        latest_date = await self.db.scalar(select(func.max(FactCurrencyRate.date_id)))
        if not latest_date:
            return [], None
        result = await self.db.execute(
            select(FactCurrencyRate)
            .where(FactCurrencyRate.date_id == latest_date)
            .order_by(FactCurrencyRate.currency_code, FactCurrencyRate.source),
        )
        rows = self._dedupe_currency_rows(list(result.scalars().all()))
        last_at: datetime | None = None
        items: list[dict[str, Any]] = []
        for r in rows:
            if r.currency_code == "EUR":
                continue
            rte = float(r.rate_to_eur)
            if rte and rte > 0:
                display = 1.0 / rte
            else:
                display = rte
            if r.fetched_at and (last_at is None or r.fetched_at > last_at):
                last_at = r.fetched_at
            items.append({
                "symbol": f"EUR/{r.currency_code}",
                "bid": Decimal(str(round(display, 6))),
                "ask": Decimal(str(round(display, 6))),
                "spread": Decimal("0"),
                "change_24h": None,
                "refreshed_at": r.fetched_at or datetime.now(timezone.utc),
            })
        return items, last_at

    async def build_crypto_api_response_async(self) -> tuple[list[dict[str, Any]], datetime | None, bool]:
        """Build MarketsCryptoResponse-compatible items."""
        latest_date = await self.db.scalar(select(func.max(FactCryptoPrice.date_id)))
        if not latest_date:
            return [], None, False
        result = await self.db.execute(
            select(FactCryptoPrice)
            .where(FactCryptoPrice.date_id == latest_date)
            .order_by(nullslast(asc(FactCryptoPrice.rank)), FactCryptoPrice.symbol),
        )
        rows = self._dedupe_crypto_rows(list(result.scalars().all()))
        last_at: datetime | None = None
        items: list[dict[str, Any]] = []
        for r in rows:
            if r.fetched_at and (last_at is None or r.fetched_at > last_at):
                last_at = r.fetched_at
            items.append({
                "symbol": r.symbol,
                "price": Decimal(str(float(r.price_usd))),
                "change_24h": float(r.change_24h_pct) if r.change_24h_pct is not None else None,
                "market_cap": Decimal(str(float(r.market_cap_usd))) if r.market_cap_usd is not None else None,
                "refreshed_at": r.fetched_at or datetime.now(timezone.utc),
            })
        return items, last_at, False


_cache: dict[str, tuple[object, float]] = {}
DEFAULT_TTL = 7200


def _get_cached(key: str, ttl: int = DEFAULT_TTL) -> object | None:
    if key in _cache:
        value, ts = _cache[key]
        if time.time() - ts < ttl:
            return value
    return None


def _set_cached(key: str, value: object) -> None:
    _cache[key] = (value, time.time())


def get_cache_info() -> dict:
    now = time.time()
    return {
        key: {
            "age_seconds": int(now - ts),
            "expired": (now - ts) > DEFAULT_TTL,
        }
        for key, (_, ts) in _cache.items()
    }


async def fetch_forex_rates(base: str = "EUR") -> list[dict]:
    cached = _get_cached(f"forex_{base}")
    if cached is not None:
        return cached

    from app.modules.market_data.providers.forex_adapter import ForexUnifiedAdapter

    try:
        adapter = ForexUnifiedAdapter(timeout=15.0)
        items = await adapter.fetch()
        normalized = []
        for dto in items:
            pair = dto.symbol.upper()
            if not pair.startswith(f"{base.upper()}/"):
                continue
            normalized.append({
                "pair": pair,
                "rate": round(float(dto.bid), 6),
                "change_24h": dto.change_24h,
            })
        normalized.sort(key=lambda row: row["pair"])
        _set_cached(f"forex_{base}", normalized)
        logger.info("Forex rates fetched via unified adapter: %d pairs (base=%s)", len(normalized), base)
        return normalized
    except Exception as error:
        logger.error("Forex unified provider error: %s", error)
        return _get_cached(f"forex_{base}", ttl=86400) or []


async def fetch_crypto_prices() -> tuple[list[dict], bool]:
    cached = _get_cached("crypto")
    if cached is not None:
        return (cached, True)

    from app.modules.market_data.providers.crypto_adapter import CryptoUnifiedAdapter

    adapter = CryptoUnifiedAdapter(timeout=15.0)
    items = await adapter.fetch()

    result = [
        {
            "symbol": dto.symbol,
            "name": dto.symbol,
            "price": float(dto.price),
            "change_24h": round(dto.change_24h, 2) if dto.change_24h is not None else None,
            "market_cap": float(dto.market_cap) if dto.market_cap is not None else None,
            "volume_24h": None,
            "image": "",
        }
        for dto in items
    ]

    _set_cached("crypto", result)
    logger.info("Crypto prices fetched: %d coins", len(result))
    return (result, False)


GOLDAPI_TTL = 129600
ALPHA_VANTAGE_TTL = 14400  # 4h — free tier 25 req/day; 1 req per 4h keeps under limit
GOLDAPI_METALS: list[tuple[str, str]] = [
    ("Gold", "XAU"),
    ("Silver", "XAG"),
    ("Platinum", "XPT"),
    ("Palladium", "XPD"),
]


async def _fetch_one_metal(
    client: httpx.AsyncClient,
    symbol: str,
    name: str,
    api_key: str,
) -> dict | None:
    try:
        resp = await client.get(
            f"https://www.goldapi.io/api/{symbol}/USD",
            headers={"x-access-token": api_key},
        )
        resp.raise_for_status()
        data = resp.json()
        price = float(data.get("price", 0))
        chp = data.get("chp")
        change_24h = round(float(chp), 2) if chp is not None else None
        return {
            "name": name,
            "symbol": symbol,
            "price": round(price, 2),
            "unit": "oz",
            "change_24h": change_24h,
        }
    except httpx.HTTPStatusError as error:
        if error.response.status_code in (403, 429):
            logger.warning(
                "GoldAPI %s: %s. Using cached data from DB.",
                symbol,
                "403 Forbidden" if error.response.status_code == 403 else "429 Rate limited",
            )
        else:
            logger.warning("GoldAPI %s fetch failed: %s", symbol, error)
        return None
    except Exception as error:
        logger.warning("GoldAPI %s fetch failed: %s", symbol, error)
        return None


async def fetch_metals() -> dict:
    cached = _get_cached("commodities_metals", ttl=GOLDAPI_TTL)
    if cached is not None:
        return cached

    settings = Settings()
    api_key = (settings.goldapi_key or "").strip()
    if not api_key:
        result = {"items": [], "error": "GOLDAPI_KEY not configured"}
        _set_cached("commodities_metals", result)
        return result

    try:
        result_items: list[dict] = []
        async with httpx.AsyncClient(timeout=15.0) as client:
            tasks = [
                _fetch_one_metal(client, symbol, name, api_key)
                for name, symbol in GOLDAPI_METALS
            ]
            metals = await asyncio.gather(*tasks)

        for item in metals:
            if item is not None:
                result_items.append(item)

        result = {"items": result_items, "error": None}
        if not result_items:
            result["error"] = (
                "Metals unavailable. Set GOLDAPI_KEY in Railway; 403 usually means invalid key or quota exceeded."
            )
        _set_cached("commodities_metals", result)
        logger.info("Metals fetched: %d items from goldapi.io", len(result_items))
        return result
    except Exception as error:
        err_msg = f"GoldAPI error: {error}"
        result = {"items": [], "error": err_msg}
        _set_cached("commodities_metals", result)
        return result


# 6 symbols: 4 metals (GoldAPI) + 2 energy (Alpha Vantage). 4 req/day × 6 = 24, fits free tier.
ALPHA_VANTAGE_TICKERS: list[tuple[str, str, str]] = [
    ("Crude Oil (WTI)", "WTI", "bbl"),
    ("Crude Oil (Brent)", "BRENT", "bbl"),
]
ALPHA_VANTAGE_FUNCTIONS: dict[str, str] = {
    "WTI": "WTI",
    "BRENT": "BRENT",
}


async def _fetch_alpha_vantage(
    client: httpx.AsyncClient,
    function: str,
    name: str,
    symbol: str,
    unit: str,
    api_key: str,
) -> dict | None:
    try:
        url = f"https://www.alphavantage.co/query?function={function}&interval=daily&apikey={api_key}"
        resp = await client.get(url)
        resp.raise_for_status()
        data = resp.json()
        err_msg = data.get("Error Message") or data.get("Note")
        if err_msg:
            logger.warning("Alpha Vantage %s: API message: %s", symbol, err_msg[:200])
            return None
        data_list = data.get("data")
        if not isinstance(data_list, list) or len(data_list) < 2:
            logger.warning("Alpha Vantage %s: insufficient data", symbol)
            return None
        latest = float(data_list[0].get("value", 0))
        prev = float(data_list[1].get("value", 0))
        if prev == 0:
            change_24h = None
        else:
            change_24h = round(((latest - prev) / prev) * 100, 2)
        return {
            "name": name,
            "symbol": symbol,
            "price": round(latest, 2),
            "unit": unit,
            "change_24h": change_24h,
        }
    except Exception as error:
        logger.warning("Alpha Vantage %s fetch failed: %s", symbol, error)
        return None


async def fetch_energy() -> dict:
    cached = _get_cached("commodities_energy", ttl=ALPHA_VANTAGE_TTL)
    if cached is not None:
        return cached

    settings = Settings()
    api_key = (settings.alpha_vantage_key or "").strip()
    if not api_key:
        result = {"items": [], "error": "ALPHA_VANTAGE_KEY not configured"}
        _set_cached("commodities_energy", result)
        return result

    try:
        result_items: list[dict] = []
        async with httpx.AsyncClient(timeout=15.0) as client:
            for name, symbol, unit in ALPHA_VANTAGE_TICKERS:
                func = ALPHA_VANTAGE_FUNCTIONS[symbol]
                item = await _fetch_alpha_vantage(client, func, name, symbol, unit, api_key)
                if item is not None:
                    result_items.append(item)

        result = {"items": result_items, "error": None}
        if not result_items:
            result["error"] = (
                "Energy data unavailable. Check ALPHA_VANTAGE_KEY in Railway; free tier is 5 calls/min."
            )
        _set_cached("commodities_energy", result)
        logger.info("Energy fetched: %d items from Alpha Vantage", len(result_items))
        return result
    except Exception as error:
        err_msg = f"Alpha Vantage error: {error}"
        result = {"items": [], "error": err_msg}
        _set_cached("commodities_energy", result)
        return result


async def fetch_commodities() -> tuple[list[dict], str | None, bool]:
    cached = _get_cached("commodities", ttl=ALPHA_VANTAGE_TTL)
    if cached is not None:
        return (cached, None, True)

    from app.modules.market_data.providers.commodities_adapter import CommoditiesUnifiedAdapter

    try:
        adapter = CommoditiesUnifiedAdapter(timeout=15.0)
        items = await adapter.fetch()
        normalized_items = [
            {
                "name": dto.name or dto.symbol,
                "symbol": dto.symbol,
                "price": float(dto.price),
                "unit": dto.unit or "",
                "change_24h": dto.change_24h,
            }
            for dto in items
        ]
        _set_cached("commodities", normalized_items)
        if not normalized_items:
            return ([], "Commodities providers unavailable (Gold API and Alpha Vantage/Yahoo)", False)
        return (normalized_items, None, False)
    except Exception as error:
        logger.warning("Unified commodities fetch failed: %s", error)
        fallback = _get_cached("commodities", ttl=GOLDAPI_TTL) or []
        if fallback:
            return (fallback, "Using cached commodities data", True)
        return ([], "Commodities providers unavailable (Gold API and Alpha Vantage/Yahoo)", False)


def _fuel_facts_to_legacy_dict(rows: list[dict[str, Any]], country_code: str) -> dict[str, Any]:
    """Map fact_fuel_price rows to legacy flat dict used by dashboard clients."""
    currency = rows[0]["currency_code"]
    label = country_code
    fetched = rows[0].get("fetched_at")
    if isinstance(fetched, datetime):
        updated_str = fetched.isoformat()
    else:
        updated_str = str(fetched) if fetched else ""
    out: dict[str, Any] = {
        "country": label,
        "currency": currency,
        "unit": "L",
        "updated": updated_str,
    }
    for r in rows:
        out[r["fuel_type"]] = r["price_local"]
    return out


def _legacy_ticker_rows_from_db(rows: list[dict[str, Any]]) -> list[dict]:
    """Convert MarketDataService.get_ticker rows to legacy ticker bar shape."""
    items: list[dict] = []
    for row in rows:
        t = row["type"]
        if t == "forex":
            items.append({
                "type": "forex",
                "label": row["symbol"],
                "value": row["price"],
                "change": row.get("change_pct"),
                "prefix": "",
                "suffix": "",
            })
        elif t == "crypto":
            items.append({
                "type": "crypto",
                "label": row["symbol"],
                "value": row["price"],
                "change": row.get("change_pct"),
                "prefix": "$",
                "suffix": "",
            })
        elif t == "commodity":
            unit = row.get("unit") or ""
            items.append({
                "type": "commodity",
                "label": row["name"],
                "value": row["price"],
                "change": row.get("change_pct"),
                "prefix": "$",
                "suffix": f"/{unit}" if unit else "",
            })
        elif t == "fuel":
            cc = row.get("currency_code", "")
            items.append({
                "type": "fuel",
                "label": row["symbol"],
                "value": row["price"],
                "change": row.get("change_pct"),
                "prefix": "",
                "suffix": f" {cc}/L" if cc else "",
            })
    return items


async def get_fuel_prices(country_code: str, db: AsyncSession | None = None) -> dict | None:
    """Get fuel prices from fact_fuel_price only (requires db session)."""
    code = country_code.upper()
    if db is None:
        return None
    mds = MarketDataService(db)
    raw = await mds.get_fuel(code)
    if raw:
        return _fuel_facts_to_legacy_dict(raw, code)
    return None


async def get_ticker_data(
    country_code: str = "UA",
    db: AsyncSession | None = None,
    forex_favorites: Iterable[str] | None = None,
    crypto_favorites: Iterable[str] | None = None,
    commodity_favorites: Iterable[str] | None = None,
) -> list[dict]:
    """Assemble ticker data for the scrolling bar. Uses v2 facts when available."""
    forex_set = {value.strip().upper() for value in (forex_favorites or []) if value}
    crypto_set = {value.strip().upper() for value in (crypto_favorites or []) if value}
    commodity_set = {value.strip().upper() for value in (commodity_favorites or []) if value}

    if db is not None:
        mds = MarketDataService(db)
        db_rows = await mds.get_ticker(
            country_code,
            forex_favorites=forex_set,
            crypto_favorites=crypto_set,
            commodity_favorites=commodity_set,
        )
        if db_rows:
            return _legacy_ticker_rows_from_db(db_rows)

    items: list[dict] = []

    forex = await fetch_forex_rates("EUR")
    for pair in forex[:6]:
        symbol = str(pair["pair"]).upper()
        if forex_set and symbol not in forex_set:
            continue
        items.append({
            "type": "forex",
            "label": symbol,
            "value": pair["rate"],
            "change": pair.get("change_24h"),
            "prefix": "",
            "suffix": "",
        })

    try:
        crypto_data, _ = await fetch_crypto_prices()
        for coin in crypto_data[:5]:
            symbol = str(coin["symbol"]).upper()
            if crypto_set and symbol not in crypto_set:
                continue
            items.append({
                "type": "crypto",
                "label": symbol,
                "value": coin["price"],
                "change": coin["change_24h"],
                "prefix": "$",
                "suffix": "",
            })
    except Exception:
        pass

    try:
        commodities, _, _ = await fetch_commodities()
        for item in (commodities or [])[:3]:
            symbol = str(item.get("symbol", "")).upper()
            if commodity_set and symbol not in commodity_set:
                continue
            name = item.get("name") or item.get("symbol", "")
            items.append({
                "type": "commodity",
                "label": name,
                "value": item["price"],
                "change": item.get("change_24h"),
                "prefix": "$",
                "suffix": f"/{item.get('unit', '')}",
            })
    except Exception:
        pass

    fuel = await get_fuel_prices(country_code, db=None)
    if fuel:
        items.append({
            "type": "fuel",
            "label": f"Gasoline 95 ({fuel['country']})",
            "value": fuel["gasoline_95"],
            "change": None,
            "prefix": "",
            "suffix": f" {fuel['currency']}/{fuel['unit']}",
        })
        items.append({
            "type": "fuel",
            "label": f"Diesel ({fuel['country']})",
            "value": fuel["diesel"],
            "change": None,
            "prefix": "",
            "suffix": f" {fuel['currency']}/{fuel['unit']}",
        })

    return items


class MarketsService:
    """Markets domain: user preferences (JSONB), commodities from v2 facts, refresh metadata."""

    _PREF_KEYS = frozenset({
        "dashboard_widgets",
        "forex_favorites",
        "crypto_favorites",
        "commodity_favorites",
        "favorite_instrument_ids",
    })

    def __init__(self, db: AsyncSession, user_id):
        self.db = db
        self.user_id = user_id

    async def _get_user(self) -> User:
        result = await self.db.execute(select(User).where(User.id == self.user_id))
        user = result.scalar_one_or_none()
        if user is None:
            raise ValueError("User not found")
        return user

    async def get_commodities_from_db(self) -> tuple[list[dict], datetime | None]:
        mds = MarketDataService(self.db)
        rows = await mds.get_commodities()
        if not rows:
            return [], None
        last_at: datetime | None = None
        raw_items: list[dict] = []
        for c in rows:
            fa = c.get("fetched_at")
            if isinstance(fa, datetime):
                if last_at is None or fa > last_at:
                    last_at = fa
            ref = fa if isinstance(fa, datetime) else datetime.now(timezone.utc)
            raw_items.append({
                "symbol": c["symbol"],
                "name": c.get("name"),
                "price": Decimal(str(c["price_usd"])),
                "change_24h": c.get("change_24h_pct"),
                "unit": c.get("unit"),
                "refreshed_at": ref,
            })
        return raw_items, last_at

    async def get_preferences(self) -> dict:
        user = await self._get_user()
        mds = MarketDataService(self.db)
        return await mds.get_preferences(user)

    async def update_preferences(self, **updates: Any) -> dict:
        user = await self._get_user()
        mds = MarketDataService(self.db)
        clean = {k: v for k, v in updates.items() if k in self._PREF_KEYS and v is not None}
        return await mds.update_preferences(user, clean)

    async def get_refresh_metadata(self) -> list[dict]:
        mds = MarketDataService(self.db)
        return await mds.get_refresh_metadata()

    async def get_available_instruments(self) -> dict[str, list[dict[str, str]]]:
        """Return available instrument lists for user-configurable ticker widgets."""
        mds = MarketDataService(self.db)
        forex, crypto, commodities = await asyncio.gather(
            mds.get_available_forex_instruments(),
            mds.get_available_crypto_instruments(),
            mds.get_available_commodity_instruments(),
        )
        return {
            "forex": forex,
            "crypto": crypto,
            "commodities": commodities,
        }

    async def get_category_analytics(self) -> dict:
        return {"items": [], "last_refreshed_at": None}

    async def get_marketplace_analytics(self) -> dict:
        return {"items": [], "last_refreshed_at": None}

    async def get_opportunities(self) -> dict:
        return {"items": [], "last_refreshed_at": None}
