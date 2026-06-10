"""DB read facade for the market_data v2 star schema.

`MarketDataService` reads the latest snapshot of forex / crypto / commodity /
fuel facts and exposes the shapes consumed by `api.py`, `facade.MarketsService`,
`ticker.get_ticker_data`, and `fuel.get_fuel_prices`. It performs no external
HTTP — all upstream fetch lives in `providers/`, wrapped by `fetching.py`.
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Iterable

from sqlalchemy import asc, func, nullslast, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.app_tables import ApiLog
from app.models.core import User
from app.models.facts import (
    FactCommodityPrice,
    FactCryptoPrice,
    FactCurrencyRate,
    FactFuelPrice,
)


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
