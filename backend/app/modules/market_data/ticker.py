"""Ticker assembly for the scrolling banner widget.

`get_ticker_data` prefers v2 facts via `reader.MarketDataService.get_ticker`
and falls back to live provider data via `fetching.fetch_*` only when the DB
has no rows yet (pre-first-ingest). `_legacy_ticker_rows_from_db` converts the
reader's tuples into the legacy ticker shape consumed by `api.py /markets/ticker`.

Parity note carried from pre-M3a service.py: the live-fallback branch calls
`get_fuel_prices(country_code, db=None)`, which always returns `None`, so the
gasoline/diesel append blocks below are dead. Preserved verbatim in M3a; the
fix is a separate backlog item once the live path is removed entirely.
"""

from typing import Iterable

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.market_data.fetching import (
    fetch_commodities,
    fetch_crypto_prices,
    fetch_forex_rates,
)
from app.modules.market_data.fuel import get_fuel_prices
from app.modules.market_data.reader import MarketDataService


def _legacy_ticker_rows_from_db(rows: list[dict]) -> list[dict]:
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

    # Parity-preserved dead branch: get_fuel_prices(db=None) returns None, so
    # the gasoline_95 / diesel rows below never append. Do NOT fix in M3a.
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
