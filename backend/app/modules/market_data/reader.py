"""DB read facade for the market_data v2 star schema.

`MarketDataService` reads the latest snapshot of forex / crypto / commodity
facts and exposes the shapes consumed by `api.py`, `facade.MarketsService`,
and `ticker.get_ticker_data`. It performs no external HTTP — all upstream
fetch lives in `providers/`, wrapped by `fetching.py`.
"""

from datetime import datetime, timezone
from typing import Any, Iterable

from sqlalchemy import asc, func, nullslast, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.core import User
from app.models.facts import (
    FactCommodityPrice,
    FactCryptoPrice,
    FactCurrencyRate,
)
from app.config import Settings
from app.modules.market_data.forex_pairs import derive_forex_pairs


class MarketDataService:
    """Read forex, crypto, and commodities from v2 fact tables."""

    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def _forex_allowed_codes() -> frozenset[str]:
        return Settings().forex_allowed_currency_set

    @staticmethod
    def _currency_rows_from_facts(rows: list[FactCurrencyRate]) -> list[dict[str, Any]]:
        allowed = MarketDataService._forex_allowed_codes()
        return [
            {
                "currency_code": r.currency_code,
                "rate_to_eur": float(r.rate_to_eur),
                "rate_to_usd": float(r.rate_to_usd),
                "source": r.source,
                "fetched_at": r.fetched_at.isoformat() if r.fetched_at else None,
            }
            for r in rows
            if r.currency_code in allowed
        ]

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
        return self._currency_rows_from_facts(rows)

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

    async def get_preferences(self, user: User) -> dict[str, Any]:
        """User preferences from users.preferences JSONB."""
        prefs = user.preferences or {}
        return {
            "dashboard_widgets": prefs.get(
                "dashboard_widgets",
                ["forex", "crypto", "commodities"],
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
        """Build ticker from latest forex + crypto + commodities."""
        forex_set = {value.strip().upper() for value in (forex_favorites or []) if value}
        crypto_set = {value.strip().upper() for value in (crypto_favorites or []) if value}
        commodity_set = {value.strip().upper() for value in (commodity_favorites or []) if value}

        items: list[dict[str, Any]] = []
        if forex_set:
            forex_rows = await self.get_forex()
            for pair in derive_forex_pairs(forex_rows):
                symbol = pair["symbol"]
                if symbol.upper() not in forex_set:
                    continue
                items.append({
                    "symbol": symbol,
                    "name": symbol,
                    "price": pair["rate"],
                    "change_pct": None,
                    "type": "forex",
                })
        if crypto_set:
            for c in await self.get_crypto():
                symbol = str(c["symbol"]).upper()
                if symbol not in crypto_set:
                    continue
                items.append({
                    "symbol": symbol,
                    "name": c.get("name", c["symbol"]),
                    "price": c["price_usd"],
                    "change_pct": c.get("change_24h_pct"),
                    "type": "crypto",
                })
        if commodity_set:
            for cm in await self.get_commodities():
                symbol = str(cm["symbol"]).upper()
                if symbol not in commodity_set:
                    continue
                items.append({
                    "symbol": symbol,
                    "name": cm["name"],
                    "price": cm["price_usd"],
                    "change_pct": cm.get("change_24h_pct"),
                    "type": "commodity",
                    "unit": cm.get("unit", ""),
                })
        return items

    async def get_available_forex_instruments(self) -> list[dict[str, Any]]:
        """Return forex pair symbols available in DB for instrument selection UI."""
        rows = await self.get_forex()
        pairs = derive_forex_pairs(rows)
        options: list[dict[str, Any]] = []
        for idx, pair in enumerate(pairs):
            symbol = pair["symbol"]
            options.append({
                "symbol": symbol,
                "name": symbol,
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
