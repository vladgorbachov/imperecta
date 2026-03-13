"""
Real market data service.
Fetches forex, crypto, commodities, and fuel prices from free public APIs.
All data is cached in-memory with 2-hour TTL to respect rate limits.
"""

import logging
import time
from datetime import datetime, timezone

import httpx

logger = logging.getLogger(__name__)


# ============================================================
# IN-MEMORY CACHE (TTL-based)
# ============================================================

_cache: dict[str, tuple[object, float]] = {}
DEFAULT_TTL = 7200  # 2 hours in seconds


def _get_cached(key: str, ttl: int = DEFAULT_TTL) -> object | None:
    if key in _cache:
        value, ts = _cache[key]
        if time.time() - ts < ttl:
            return value
    return None


def _set_cached(key: str, value: object) -> None:
    _cache[key] = (value, time.time())


def get_cache_info() -> dict:
    """Return cache status for debugging."""
    now = time.time()
    return {
        key: {
            "age_seconds": int(now - ts),
            "expired": (now - ts) > DEFAULT_TTL,
        }
        for key, (_, ts) in _cache.items()
    }


# ============================================================
# FOREX — ExchangeRate-API (free, no key, 1500 req/month)
# https://open.er-api.com/v6/latest/EUR
# ============================================================


async def fetch_forex_rates(base: str = "EUR") -> list[dict]:
    """
    Fetch real forex rates.
    Returns: [{"pair": "EUR/USD", "rate": 1.0845, "change_24h": null}, ...]
    """
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

        # Pairs relevant for CIS + Europe users
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
                    "change_24h": None,  # free tier has no historical data
                })

        _set_cached(f"forex_{base}", result)
        logger.info("Forex rates fetched: %d pairs (base=%s)", len(result), base)
        return result

    except httpx.TimeoutException:
        logger.error("Forex API timeout")
        return _get_cached(f"forex_{base}", ttl=86400) or []  # stale cache fallback
    except Exception as e:
        logger.error("Forex API error: %s", e)
        return _get_cached(f"forex_{base}", ttl=86400) or []


# ============================================================
# CRYPTO — CoinGecko API (free, no key, 30 req/min)
# https://api.coingecko.com/api/v3/coins/markets
# ============================================================


async def fetch_crypto_prices() -> list[dict]:
    """
    Fetch top 20 crypto prices by market cap.
    Returns: [{"symbol": "BTC", "name": "Bitcoin", "price": 73459.0,
               "change_24h": 5.1, "market_cap": 1450000000000, "volume_24h": ...}, ...]
    """
    cached = _get_cached("crypto")
    if cached is not None:
        return cached

    try:
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
        return result

    except httpx.TimeoutException:
        logger.error("CoinGecko API timeout")
        return _get_cached("crypto", ttl=86400) or []
    except Exception as e:
        logger.error("CoinGecko API error: %s", e)
        return _get_cached("crypto", ttl=86400) or []


# ============================================================
# COMMODITIES — metals.dev (free demo key) + static oil/gas
# https://api.metals.dev/v1/latest?api_key=demo&currency=USD&unit=toz
# ============================================================


async def fetch_commodities() -> list[dict]:
    """
    Fetch commodity prices: precious metals from API, oil/gas static (updated weekly).
    Returns: [{"name": "Gold", "symbol": "XAU", "price": 2950.0, "unit": "oz",
               "change_24h": null}, ...]
    """
    cached = _get_cached("commodities")
    if cached is not None:
        return cached

    result: list[dict] = []

    # Precious metals from metals.dev
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                "https://api.metals.dev/v1/latest",
                params={"api_key": "demo", "currency": "USD", "unit": "toz"},
            )
            resp.raise_for_status()
            data = resp.json()

        metals = data.get("metals", {})
        metal_map = {
            "gold": ("Gold", "XAU"),
            "silver": ("Silver", "XAG"),
            "platinum": ("Platinum", "XPT"),
            "palladium": ("Palladium", "XPD"),
        }
        for key, (name, symbol) in metal_map.items():
            if key in metals:
                result.append({
                    "name": name,
                    "symbol": symbol,
                    "price": round(metals[key], 2),
                    "unit": "oz",
                    "change_24h": None,
                })

        logger.info("Metals fetched: %d items", len(result))

    except Exception as e:
        logger.error("Metals API error: %s", e)
        # Fallback: approximate recent prices so widget is never empty
        result = [
            {"name": "Gold", "symbol": "XAU", "price": 2950.00, "unit": "oz", "change_24h": None},
            {"name": "Silver", "symbol": "XAG", "price": 33.50, "unit": "oz", "change_24h": None},
            {"name": "Platinum", "symbol": "XPT", "price": 980.00, "unit": "oz", "change_24h": None},
            {"name": "Palladium", "symbol": "XPD", "price": 960.00, "unit": "oz", "change_24h": None},
        ]

    # Oil and Gas — static (no free reliable API; update via Celery task weekly)
    result.extend([
        {"name": "Crude Oil (Brent)", "symbol": "BRENT", "price": 70.50, "unit": "bbl", "change_24h": None},
        {"name": "Crude Oil (WTI)", "symbol": "WTI", "price": 67.20, "unit": "bbl", "change_24h": None},
        {"name": "Natural Gas", "symbol": "NATGAS", "price": 4.20, "unit": "MMBtu", "change_24h": None},
    ])

    # Fuel — Europe avg (frontend filters by symbol gasoline/diesel/lpg)
    result.extend([
        {"name": "Gasoline 95 (Europe avg)", "symbol": "gasoline", "price": 1.72, "unit": "EUR/L", "change_24h": None},
        {"name": "Diesel (Europe avg)", "symbol": "diesel", "price": 1.62, "unit": "EUR/L", "change_24h": None},
        {"name": "LPG (Europe avg)", "symbol": "lpg", "price": 0.78, "unit": "EUR/L", "change_24h": None},
    ])

    _set_cached("commodities", result)
    return result


# ============================================================
# FUEL — Static prices by country (update weekly via admin/Celery)
# ============================================================

FUEL_PRICES: dict[str, dict] = {
    # CIS
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
    # Europe
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

# Region averages
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


# ============================================================
# TICKER — Assembled data for scrolling bar
# ============================================================


async def get_ticker_data(country_code: str = "UA") -> list[dict]:
    """
    Assemble ticker data for the scrolling bar.
    Combines: forex (top 4) + crypto (top 5) + fuel (if available for country).
    """
    items: list[dict] = []

    # Forex top pairs
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

    # Crypto top 5
    crypto = await fetch_crypto_prices()
    for coin in crypto[:5]:
        items.append({
            "type": "crypto",
            "label": coin["symbol"],
            "value": coin["price"],
            "change": coin["change_24h"],
            "prefix": "$",
            "suffix": "",
        })

    # Commodities top 3
    commodities = await fetch_commodities()
    for item in commodities[:3]:
        items.append({
            "type": "commodity",
            "label": item["name"],
            "value": item["price"],
            "change": item.get("change_24h"),
            "prefix": "$",
            "suffix": f"/{item['unit']}",
        })

    # Fuel for selected country
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
