"""Ticker assembly for the scrolling banner widget.

`get_ticker_data` prefers v2 facts via `reader.MarketDataService.get_ticker`
and falls back to live provider data via `fetching.fetch_*` only when the DB
has no rows yet (pre-first-ingest). `_legacy_ticker_rows_from_db` converts the
reader's tuples into the legacy ticker shape consumed by `api.py /markets/ticker`.

The live-fallback branch mirrors `reader.get_ticker` parity: exactly-saved
favorites per class, empty class emits nothing, no slice caps, and
forex crosses/inverses via `derive_forex_pairs` over live EUR-base rates.
"""

from typing import Any, Iterable

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.market_data.fetching import (
    fetch_commodities,
    fetch_crypto_prices,
    fetch_forex_rates,
)
from app.modules.market_data.forex_pairs import derive_forex_pairs
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
    return items


def _currency_rows_from_live_forex(live_pairs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Map fetch_forex_rates EUR-base rows to the shape `get_forex()` returns.

    Live ``EUR/X`` rate R is units of X per 1 EUR; ``rate_to_eur`` for X is
    EUR per 1 X (= 1/R), matching ``FactCurrencyRate.rate_to_eur`` semantics.
    """
    rows: list[dict[str, Any]] = []
    for pair in live_pairs:
        pair_code = str(pair.get("pair", "")).upper()
        if not pair_code.startswith("EUR/"):
            continue
        quote = pair_code.split("/", 1)[1]
        rate = float(pair.get("rate", 0))
        if rate <= 0:
            continue
        rows.append({
            "currency_code": quote,
            "rate_to_eur": 1.0 / rate,
            "rate_to_usd": 0.0,
            "source": "live",
            "fetched_at": None,
        })
    return rows


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

    if forex_set:
        forex_live = await fetch_forex_rates("EUR")
        currency_rows = _currency_rows_from_live_forex(forex_live)
        for pair in derive_forex_pairs(currency_rows):
            symbol = pair["symbol"]
            if symbol.upper() not in forex_set:
                continue
            items.append({
                "type": "forex",
                "label": symbol,
                "value": pair["rate"],
                "change": None,
                "prefix": "",
                "suffix": "",
            })

    if crypto_set:
        try:
            crypto_data, _ = await fetch_crypto_prices()
            for coin in crypto_data:
                symbol = str(coin["symbol"]).upper()
                if symbol not in crypto_set:
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

    if commodity_set:
        try:
            commodities, _, _ = await fetch_commodities()
            for item in commodities or []:
                symbol = str(item.get("symbol", "")).upper()
                if symbol not in commodity_set:
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

    return items
