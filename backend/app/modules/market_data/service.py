"""
Real market data service and markets domain service.
Fetches forex, crypto, commodities, and fuel prices from APIs.
"""

import asyncio
import logging
import time
from datetime import datetime

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models import (
    MarketsCategoryAnalytics,
    MarketsMarketplaceAnalytics,
    MarketsOpportunityBlock,
)
from app.modules.market_data.models import (
    MarketsPreferences,
    MarketsRefreshLog,
    MarketsRefreshStatus,
)

logger = logging.getLogger(__name__)

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

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(f"https://open.er-api.com/v6/latest/{base}")
            resp.raise_for_status()
            data = resp.json()

        if data.get("result") != "success":
            logger.error("ExchangeRate API error: %s", data.get("error-type"))
            return []

        rates = data.get("rates", {})
        targets = [
            "USD", "GBP", "CHF", "JPY", "CNY",
            "RUB", "UAH", "KZT", "BYN", "GEL", "AMD", "UZS", "MDL",
            "PLN", "RON", "HUF", "CZK", "BGN", "TRY", "SEK", "NOK", "DKK",
        ]

        result = []
        for cur in targets:
            if cur in rates and cur != base:
                result.append({
                    "pair": f"{base}/{cur}",
                    "rate": round(rates[cur], 4),
                    "change_24h": None,
                })

        _set_cached(f"forex_{base}", result)
        logger.info("Forex rates fetched: %d pairs (base=%s)", len(result), base)
        return result
    except httpx.TimeoutException:
        logger.error("Forex API timeout")
        return _get_cached(f"forex_{base}", ttl=86400) or []
    except Exception as error:
        logger.error("Forex API error: %s", error)
        return _get_cached(f"forex_{base}", ttl=86400) or []


async def fetch_crypto_prices() -> tuple[list[dict], bool]:
    cached = _get_cached("crypto")
    if cached is not None:
        return (cached, True)

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(
            "https://api.coingecko.com/api/v3/coins/markets",
            params={
                "vs_currency": "usd",
                "order": "market_cap_desc",
                "per_page": 20,
                "page": 1,
                "sparkline": "false",
                "price_change_percentage": "24h",
            },
        )
        resp.raise_for_status()
        data = resp.json()

    result = []
    for coin in data:
        result.append({
            "symbol": (coin.get("symbol") or "").upper(),
            "name": coin.get("name", ""),
            "price": coin.get("current_price") or 0,
            "change_24h": round(coin.get("price_change_percentage_24h") or 0, 2),
            "market_cap": coin.get("market_cap") or 0,
            "volume_24h": coin.get("total_volume") or 0,
            "image": coin.get("image", ""),
        })

    _set_cached("crypto", result)
    logger.info("Crypto prices fetched: %d coins", len(result))
    return (result, False)


GOLDAPI_TTL = 129600
ALPHA_VANTAGE_TTL = 86400
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
        if error.response.status_code == 403:
            logger.warning(
                "GoldAPI %s: 403 Forbidden. Set GOLDAPI_KEY in Railway; key may be invalid or quota exceeded.",
                symbol,
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


ALPHA_VANTAGE_TICKERS: list[tuple[str, str, str]] = [
    ("Crude Oil (WTI)", "WTI", "bbl"),
    ("Crude Oil (Brent)", "BRENT", "bbl"),
    ("Natural Gas", "NATGAS", "MMBtu"),
]
ALPHA_VANTAGE_FUNCTIONS: dict[str, str] = {
    "WTI": "WTI",
    "BRENT": "BRENT",
    "NATGAS": "NATURAL_GAS",
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
    metals = await fetch_metals()
    energy = await fetch_energy()

    all_items = metals.get("items", []) + energy.get("items", [])
    errors = [e for e in [metals.get("error"), energy.get("error")] if e]
    error_msg = "; ".join(errors) if errors else None
    return (all_items, error_msg, False)


# TODO: Replace hardcoded fuel prices with external API source.
FUEL_PRICES: dict[str, dict] = {
    "RU": {"country": "Russia", "gasoline_95": 54.0, "diesel": 60.5, "lpg": 28.0, "currency": "RUB", "unit": "L", "updated": "2026-03-01"},
    "UA": {"country": "Ukraine", "gasoline_95": 54.5, "diesel": 52.0, "lpg": 22.5, "currency": "UAH", "unit": "L", "updated": "2026-03-01"},
    "KZ": {"country": "Kazakhstan", "gasoline_95": 205.0, "diesel": 295.0, "lpg": 85.0, "currency": "KZT", "unit": "L", "updated": "2026-03-01"},
    "BY": {"country": "Belarus", "gasoline_95": 2.34, "diesel": 2.42, "lpg": 1.15, "currency": "BYN", "unit": "L", "updated": "2026-03-01"},
    "GE": {"country": "Georgia", "gasoline_95": 3.10, "diesel": 3.30, "lpg": 1.40, "currency": "GEL", "unit": "L", "updated": "2026-03-01"},
    "AM": {"country": "Armenia", "gasoline_95": 490.0, "diesel": 580.0, "lpg": 220.0, "currency": "AMD", "unit": "L", "updated": "2026-03-01"},
    "AZ": {"country": "Azerbaijan", "gasoline_95": 1.0, "diesel": 0.85, "lpg": 0.60, "currency": "AZN", "unit": "L", "updated": "2026-03-01"},
    "MD": {"country": "Moldova", "gasoline_95": 25.5, "diesel": 23.0, "lpg": 13.5, "currency": "MDL", "unit": "L", "updated": "2026-03-01"},
    "UZ": {"country": "Uzbekistan", "gasoline_95": 10500.0, "diesel": 11000.0, "lpg": 5500.0, "currency": "UZS", "unit": "L", "updated": "2026-03-01"},
    "KG": {"country": "Kyrgyzstan", "gasoline_95": 58.0, "diesel": 62.0, "lpg": 30.0, "currency": "KGS", "unit": "L", "updated": "2026-03-01"},
    "TJ": {"country": "Tajikistan", "gasoline_95": 12.5, "diesel": 13.0, "lpg": 7.0, "currency": "TJS", "unit": "L", "updated": "2026-03-01"},
    "TM": {"country": "Turkmenistan", "gasoline_95": 1.5, "diesel": 1.7, "lpg": 0.9, "currency": "TMT", "unit": "L", "updated": "2026-03-01"},
    "DE": {"country": "Germany", "gasoline_95": 1.72, "diesel": 1.58, "lpg": 0.72, "currency": "EUR", "unit": "L", "updated": "2026-03-01"},
    "FR": {"country": "France", "gasoline_95": 1.82, "diesel": 1.68, "lpg": 0.85, "currency": "EUR", "unit": "L", "updated": "2026-03-01"},
    "PL": {"country": "Poland", "gasoline_95": 6.35, "diesel": 6.10, "lpg": 2.85, "currency": "PLN", "unit": "L", "updated": "2026-03-01"},
    "RO": {"country": "Romania", "gasoline_95": 7.20, "diesel": 7.50, "lpg": 3.30, "currency": "RON", "unit": "L", "updated": "2026-03-01"},
    "HU": {"country": "Hungary", "gasoline_95": 615.0, "diesel": 620.0, "lpg": 290.0, "currency": "HUF", "unit": "L", "updated": "2026-03-01"},
    "BG": {"country": "Bulgaria", "gasoline_95": 2.55, "diesel": 2.65, "lpg": 1.20, "currency": "BGN", "unit": "L", "updated": "2026-03-01"},
    "CZ": {"country": "Czech Republic", "gasoline_95": 37.5, "diesel": 36.0, "lpg": 16.5, "currency": "CZK", "unit": "L", "updated": "2026-03-01"},
    "SK": {"country": "Slovakia", "gasoline_95": 1.62, "diesel": 1.52, "lpg": 0.75, "currency": "EUR", "unit": "L", "updated": "2026-03-01"},
    "HR": {"country": "Croatia", "gasoline_95": 1.55, "diesel": 1.60, "lpg": 0.78, "currency": "EUR", "unit": "L", "updated": "2026-03-01"},
    "SI": {"country": "Slovenia", "gasoline_95": 1.58, "diesel": 1.55, "lpg": 0.82, "currency": "EUR", "unit": "L", "updated": "2026-03-01"},
    "RS": {"country": "Serbia", "gasoline_95": 198.0, "diesel": 205.0, "lpg": 90.0, "currency": "RSD", "unit": "L", "updated": "2026-03-01"},
    "TR": {"country": "Turkey", "gasoline_95": 42.5, "diesel": 38.0, "lpg": 15.5, "currency": "TRY", "unit": "L", "updated": "2026-03-01"},
    "GR": {"country": "Greece", "gasoline_95": 1.85, "diesel": 1.62, "lpg": 0.88, "currency": "EUR", "unit": "L", "updated": "2026-03-01"},
    "NL": {"country": "Netherlands", "gasoline_95": 2.05, "diesel": 1.75, "lpg": 0.90, "currency": "EUR", "unit": "L", "updated": "2026-03-01"},
    "BE": {"country": "Belgium", "gasoline_95": 1.75, "diesel": 1.70, "lpg": 0.65, "currency": "EUR", "unit": "L", "updated": "2026-03-01"},
    "AT": {"country": "Austria", "gasoline_95": 1.55, "diesel": 1.58, "lpg": 0.72, "currency": "EUR", "unit": "L", "updated": "2026-03-01"},
    "IT": {"country": "Italy", "gasoline_95": 1.82, "diesel": 1.72, "lpg": 0.75, "currency": "EUR", "unit": "L", "updated": "2026-03-01"},
    "ES": {"country": "Spain", "gasoline_95": 1.58, "diesel": 1.48, "lpg": 0.72, "currency": "EUR", "unit": "L", "updated": "2026-03-01"},
    "PT": {"country": "Portugal", "gasoline_95": 1.72, "diesel": 1.55, "lpg": 0.80, "currency": "EUR", "unit": "L", "updated": "2026-03-01"},
    "SE": {"country": "Sweden", "gasoline_95": 17.5, "diesel": 18.2, "lpg": 8.5, "currency": "SEK", "unit": "L", "updated": "2026-03-01"},
    "NO": {"country": "Norway", "gasoline_95": 19.8, "diesel": 18.5, "lpg": 9.0, "currency": "NOK", "unit": "L", "updated": "2026-03-01"},
    "DK": {"country": "Denmark", "gasoline_95": 13.5, "diesel": 12.8, "lpg": 6.5, "currency": "DKK", "unit": "L", "updated": "2026-03-01"},
    "FI": {"country": "Finland", "gasoline_95": 1.88, "diesel": 1.72, "lpg": 0.95, "currency": "EUR", "unit": "L", "updated": "2026-03-01"},
    "LV": {"country": "Latvia", "gasoline_95": 1.65, "diesel": 1.55, "lpg": 0.68, "currency": "EUR", "unit": "L", "updated": "2026-03-01"},
    "LT": {"country": "Lithuania", "gasoline_95": 1.55, "diesel": 1.48, "lpg": 0.70, "currency": "EUR", "unit": "L", "updated": "2026-03-01"},
    "EE": {"country": "Estonia", "gasoline_95": 1.62, "diesel": 1.52, "lpg": 0.75, "currency": "EUR", "unit": "L", "updated": "2026-03-01"},
    "GB": {"country": "United Kingdom", "gasoline_95": 1.42, "diesel": 1.48, "lpg": 0.68, "currency": "GBP", "unit": "L", "updated": "2026-03-01"},
    "IE": {"country": "Ireland", "gasoline_95": 1.72, "diesel": 1.65, "lpg": 0.85, "currency": "EUR", "unit": "L", "updated": "2026-03-01"},
    "IS": {"country": "Iceland", "gasoline_95": 310.0, "diesel": 315.0, "lpg": 160.0, "currency": "ISK", "unit": "L", "updated": "2026-03-01"},
    "CH": {"country": "Switzerland", "gasoline_95": 1.82, "diesel": 1.88, "lpg": 0.95, "currency": "CHF", "unit": "L", "updated": "2026-03-01"},
    "BA": {"country": "Bosnia", "gasoline_95": 2.65, "diesel": 2.55, "lpg": 1.10, "currency": "BAM", "unit": "L", "updated": "2026-03-01"},
    "ME": {"country": "Montenegro", "gasoline_95": 1.52, "diesel": 1.45, "lpg": 0.72, "currency": "EUR", "unit": "L", "updated": "2026-03-01"},
    "AL": {"country": "Albania", "gasoline_95": 245.0, "diesel": 240.0, "lpg": 90.0, "currency": "ALL", "unit": "L", "updated": "2026-03-01"},
    "MK": {"country": "North Macedonia", "gasoline_95": 82.0, "diesel": 78.0, "lpg": 38.0, "currency": "MKD", "unit": "L", "updated": "2026-03-01"},
}

FUEL_REGION_AVERAGES: dict[str, dict] = {
    "EUROPE": {"country": "Europe (avg)", "gasoline_95": 1.72, "diesel": 1.62, "lpg": 0.78, "currency": "EUR", "unit": "L", "updated": "2026-03-01"},
    "CIS": {"country": "CIS (avg)", "gasoline_95": 52.0, "diesel": 55.0, "lpg": 24.0, "currency": "RUB", "unit": "L", "updated": "2026-03-01"},
}


async def get_fuel_prices(country_code: str) -> dict | None:
    """Get fuel prices for a country or region. Returns None if not found."""
    code = country_code.upper()
    if code in FUEL_REGION_AVERAGES:
        return FUEL_REGION_AVERAGES[code]
    return FUEL_PRICES.get(code)


async def get_ticker_data(country_code: str = "UA") -> list[dict]:
    """Assemble ticker data for the scrolling bar."""
    items: list[dict] = []

    forex = await fetch_forex_rates("EUR")
    for pair in forex[:6]:
        items.append({
            "type": "forex",
            "label": pair["pair"],
            "value": pair["rate"],
            "change": pair.get("change_24h"),
            "prefix": "",
            "suffix": "",
        })

    try:
        crypto_data, _ = await fetch_crypto_prices()
        for coin in crypto_data[:5]:
            items.append({
                "type": "crypto",
                "label": coin["symbol"],
                "value": coin["price"],
                "change": coin["change_24h"],
                "prefix": "$",
                "suffix": "",
            })
    except Exception:
        pass

    try:
        commodities, _, _ = await fetch_commodities()
        for item in commodities[:3]:
            items.append({
                "type": "commodity",
                "label": item["name"],
                "value": item["price"],
                "change": item.get("change_24h"),
                "prefix": "$",
                "suffix": f"/{item['unit']}",
            })
    except Exception:
        pass

    fuel = await get_fuel_prices(country_code)
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
    """Service for markets data. Uses typed schemas."""

    _NON_MARKETPLACE_IDS = frozenset({"crypto", "commodities", "forex"})

    def __init__(self, db: AsyncSession, user_id):
        self.db = db
        self.user_id = user_id

    async def get_preferences(self) -> dict:
        result = await self.db.execute(
            select(MarketsPreferences).where(MarketsPreferences.user_id == self.user_id)
        )
        prefs = result.scalar_one_or_none()
        if prefs:
            return {
                "preferred_country_code": prefs.preferred_country_code,
                "favorite_instrument_ids": prefs.favorite_instrument_ids or [],
            }
        return {
            "preferred_country_code": None,
            "favorite_instrument_ids": [],
        }

    async def update_preferences(
        self,
        preferred_country_code: str | None = None,
        favorite_instrument_ids: list[str] | None = None,
    ) -> dict:
        result = await self.db.execute(
            select(MarketsPreferences).where(MarketsPreferences.user_id == self.user_id)
        )
        prefs = result.scalar_one_or_none()
        if not prefs:
            prefs = MarketsPreferences(user_id=self.user_id)
            self.db.add(prefs)
        if preferred_country_code is not None:
            prefs.preferred_country_code = preferred_country_code
        if favorite_instrument_ids is not None:
            prefs.favorite_instrument_ids = favorite_instrument_ids
        await self.db.flush()
        await self.db.refresh(prefs)
        return {
            "preferred_country_code": prefs.preferred_country_code,
            "favorite_instrument_ids": prefs.favorite_instrument_ids or [],
        }

    async def get_refresh_metadata(self) -> list[dict]:
        result = await self.db.execute(
            select(MarketsRefreshLog).order_by(MarketsRefreshLog.started_at.desc())
        )
        rows = result.scalars().all()

        last_success: dict[str, datetime | None] = {}
        last_failed: dict[str, datetime | None] = {}
        provider: dict[str, str | None] = {}
        country_scope: dict[str, str | None] = {}
        error_message: dict[str, str | None] = {}

        for row in rows:
            refresh_type = row.refresh_type.value
            if refresh_type not in last_success:
                last_success[refresh_type] = (
                    row.completed_at if row.status == MarketsRefreshStatus.success else None
                )
            if refresh_type not in last_failed and row.status == MarketsRefreshStatus.error:
                last_failed[refresh_type] = row.completed_at
            if refresh_type not in provider:
                provider[refresh_type] = getattr(row, "provider_source", None)
            if refresh_type not in country_scope:
                country_scope[refresh_type] = getattr(row, "country_scope", None)
            if refresh_type not in error_message and row.error_message:
                error_message[refresh_type] = row.error_message

        types_seen = set(last_success.keys()) | set(last_failed.keys())
        return [
            {
                "refresh_type": refresh_type,
                "last_successful_refresh": last_success.get(refresh_type),
                "last_failed_refresh": last_failed.get(refresh_type),
                "provider_source": provider.get(refresh_type),
                "country_scope": country_scope.get(refresh_type),
                "error_message": error_message.get(refresh_type),
            }
            for refresh_type in sorted(types_seen)
        ]

    async def get_category_analytics(self) -> dict:
        result = await self.db.execute(
            select(MarketsCategoryAnalytics).order_by(
                MarketsCategoryAnalytics.refreshed_at.desc()
            )
        )
        rows = result.scalars().unique().all()
        last_at = rows[0].refreshed_at if rows else None
        items = [
            {
                "id": str(row.id),
                "category_id": row.category_id,
                "segment": row.segment,
                "metrics": row.metrics or {},
                "refreshed_at": row.refreshed_at,
            }
            for row in rows
            if (row.category_id or "").lower() not in self._NON_MARKETPLACE_IDS
        ]
        return {"items": items, "last_refreshed_at": last_at}

    async def get_marketplace_analytics(self) -> dict:
        result = await self.db.execute(
            select(MarketsMarketplaceAnalytics).order_by(
                MarketsMarketplaceAnalytics.refreshed_at.desc()
            )
        )
        rows = result.scalars().unique().all()
        last_at = rows[0].refreshed_at if rows else None
        items = [
            {
                "id": str(row.id),
                "marketplace_id": row.marketplace_id,
                "marketplace_name": row.marketplace_name,
                "metrics": row.metrics or {},
                "refreshed_at": row.refreshed_at,
            }
            for row in rows
            if (row.marketplace_id or "").lower() not in self._NON_MARKETPLACE_IDS
        ]
        items.sort(
            key=lambda x: (
                -(x["metrics"].get("item_count") or 0),
                (x["marketplace_name"] or "").lower(),
            )
        )
        return {"items": items, "last_refreshed_at": last_at}

    async def get_opportunities(self) -> dict:
        result = await self.db.execute(
            select(MarketsOpportunityBlock).order_by(
                MarketsOpportunityBlock.refreshed_at.desc()
            )
        )
        rows = result.scalars().unique().all()
        last_at = rows[0].refreshed_at if rows else None
        return {
            "items": [
                {
                    "id": str(row.id),
                    "block_type": row.block_type,
                    "title": row.title,
                    "metrics": row.metrics or {},
                    "refreshed_at": row.refreshed_at,
                }
                for row in rows
            ],
            "last_refreshed_at": last_at,
        }
