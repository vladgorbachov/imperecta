"""Persist market quotes into v2 fact tables + api_logs audit."""

import logging
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any

import calendar
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.app_tables import ApiLog
from app.models.dimensions import DimDate
from app.models.facts import FactCommodityPrice, FactCryptoPrice, FactCurrencyRate

logger = logging.getLogger(__name__)


async def _ensure_dim_date(db: AsyncSession, d: date) -> int:
    """Return dim_date.date_id for calendar day, inserting a row if missing."""
    date_id = int(d.strftime("%Y%m%d"))
    exists = await db.scalar(select(DimDate.date_id).where(DimDate.date_id == date_id))
    if exists is not None:
        return date_id
    iso_year, iso_week, iso_weekday = d.isocalendar()
    row = DimDate(
        date_id=date_id,
        full_date=d,
        year=d.year,
        quarter=(d.month - 1) // 3 + 1,
        month=d.month,
        month_name=d.strftime("%B"),
        week_iso=iso_week,
        day_of_month=d.day,
        day_of_week=iso_weekday,
        day_name=d.strftime("%A"),
        is_weekend=iso_weekday >= 6,
        is_last_day_of_month=d.day == calendar.monthrange(d.year, d.month)[1],
    )
    db.add(row)
    await db.flush()
    return date_id


def _log_ingestion(
    db: AsyncSession,
    *,
    endpoint: str,
    status: str,
    error_message: str | None = None,
) -> None:
    db.add(
        ApiLog(
            service="market_data",
            endpoint=endpoint,
            method="POST",
            status=status,
            error_message=error_message,
        )
    )


@dataclass
class ForexIngestItem:
    """Row to persist into fact_currency_rate."""

    currency_code: str
    rate_to_eur: float
    rate_to_usd: float
    source: str


@dataclass
class CryptoIngestItem:
    """Row to persist into fact_crypto_price."""

    symbol: str
    name: str | None
    price_usd: float
    market_cap_usd: float | None
    volume_24h_usd: float | None
    change_24h_pct: float | None
    source: str
    rank: int | None


@dataclass
class CommodityIngestItem:
    """Row to persist into fact_commodity_price."""

    symbol: str
    name: str
    commodity_type: str
    price_usd: float
    unit: str
    source: str
    change_24h_pct: float | None = None
    price_eur: float | None = None


class IngestionService:
    """Write forex / crypto / commodity snapshots to star schema facts."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def persist_forex(self, items: list[ForexIngestItem]) -> int:
        """Insert forex rates for today (replaces same key rows)."""
        if not items:
            return 0
        today = datetime.now(timezone.utc).date()
        today_id = await _ensure_dim_date(self.db, today)
        now = datetime.now(timezone.utc)
        n = 0
        for item in items:
            await self.db.execute(
                delete(FactCurrencyRate).where(
                    FactCurrencyRate.date_id == today_id,
                    FactCurrencyRate.currency_code == item.currency_code[:3],
                    FactCurrencyRate.source == item.source,
                ),
            )
            self.db.add(
                FactCurrencyRate(
                    date_id=today_id,
                    currency_code=item.currency_code[:3],
                    rate_to_eur=item.rate_to_eur,
                    rate_to_usd=item.rate_to_usd,
                    source=item.source,
                    fetched_at=now,
                ),
            )
            n += 1
        await _log_ingestion(self.db, endpoint="forex", status="success")
        await self.db.commit()
        return n

    async def persist_crypto(self, items: list[CryptoIngestItem]) -> int:
        """Insert crypto rows for today."""
        if not items:
            return 0
        today = datetime.now(timezone.utc).date()
        today_id = await _ensure_dim_date(self.db, today)
        now = datetime.now(timezone.utc)
        n = 0
        for item in items:
            sym = item.symbol[:20]
            await self.db.execute(
                delete(FactCryptoPrice).where(
                    FactCryptoPrice.date_id == today_id,
                    FactCryptoPrice.symbol == sym,
                    FactCryptoPrice.source == item.source,
                ),
            )
            self.db.add(
                FactCryptoPrice(
                    date_id=today_id,
                    symbol=sym,
                    name=(item.name or sym)[:100],
                    price_usd=item.price_usd,
                    market_cap_usd=item.market_cap_usd,
                    volume_24h_usd=item.volume_24h_usd,
                    change_24h_pct=item.change_24h_pct,
                    source=item.source,
                    rank=item.rank,
                    fetched_at=now,
                ),
            )
            n += 1
        await self.db.commit()
        await _log_ingestion(self.db, endpoint="crypto", status="success")
        await self.db.commit()
        return n

    async def persist_commodities(self, items: list[CommodityIngestItem]) -> int:
        """Insert commodity rows for today."""
        if not items:
            return 0
        today = datetime.now(timezone.utc).date()
        today_id = await _ensure_dim_date(self.db, today)
        now = datetime.now(timezone.utc)
        n = 0
        for item in items:
            await self.db.execute(
                delete(FactCommodityPrice).where(
                    FactCommodityPrice.date_id == today_id,
                    FactCommodityPrice.symbol == item.symbol[:20],
                    FactCommodityPrice.source == item.source,
                ),
            )
            self.db.add(
                FactCommodityPrice(
                    date_id=today_id,
                    symbol=item.symbol[:20],
                    name=item.name[:100],
                    commodity_type=item.commodity_type,
                    price_usd=item.price_usd,
                    price_eur=item.price_eur,
                    change_24h_pct=item.change_24h_pct,
                    unit=item.unit[:20],
                    source=item.source,
                    fetched_at=now,
                ),
            )
            n += 1
        await _log_ingestion(self.db, endpoint="commodities", status="success")
        await self.db.commit()
        return n

    async def ingest_all(self, include_commodities: bool = False) -> dict[str, Any]:
        """Fetch from existing adapters and persist (orchestration entrypoint)."""
        from app.modules.market_data.service import (
            fetch_crypto_prices,
            fetch_forex_rates,
            fetch_commodities,
        )

        out: dict[str, Any] = {"forex": 0, "crypto": 0, "commodities": 0}
        try:
            raw_fx = await fetch_forex_rates("EUR")
            if raw_fx:
                pairs: dict[str, float] = {}
                for row in raw_fx:
                    cur = row.get("pair", "").split("/")[-1].strip()
                    if len(cur) != 3:
                        continue
                    r = float(row.get("rate", 0))
                    if r > 0:
                        pairs[cur] = r
                usd_per_eur = pairs.get("USD")
                items: list[ForexIngestItem] = []
                for cur, rate in pairs.items():
                    if cur == "EUR":
                        continue
                    rate_to_eur = 1.0 / rate
                    if usd_per_eur:
                        rate_to_usd = usd_per_eur / rate
                    else:
                        rate_to_usd = rate_to_eur
                    items.append(
                        ForexIngestItem(
                            currency_code=cur,
                            rate_to_eur=rate_to_eur,
                            rate_to_usd=rate_to_usd,
                            source="forex_unified",
                        ),
                    )
                out["forex"] = await self.persist_forex(items)
        except Exception as exc:
            logger.exception("ingest forex: %s", exc)
            await _log_ingestion(self.db, endpoint="forex", status="error", error_message=str(exc)[:2000])
            await self.db.commit()

        try:
            raw_c, _ = await fetch_crypto_prices()
            if raw_c:
                crypto_items = [
                    CryptoIngestItem(
                        symbol=c["symbol"],
                        name=c.get("name"),
                        price_usd=float(c["price"]),
                        market_cap_usd=float(c["market_cap"]) if c.get("market_cap") else None,
                        volume_24h_usd=None,
                        change_24h_pct=float(c["change_24h"]) if c.get("change_24h") is not None else None,
                        source="crypto_unified",
                        rank=index + 1,
                    )
                    for index, c in enumerate(raw_c)
                ]
                out["crypto"] = await self.persist_crypto(crypto_items)
        except Exception as exc:
            logger.exception("ingest crypto: %s", exc)
            await _log_ingestion(self.db, endpoint="crypto", status="error", error_message=str(exc)[:2000])
            await self.db.commit()

        if include_commodities:
            try:
                comm_raw, _, _ = await fetch_commodities()
                comm_items: list[CommodityIngestItem] = []
                for c in comm_raw or []:
                    sym = str(c.get("symbol", "UNK"))[:20]
                    name = str(c.get("name", sym))[:100]
                    unit = str(c.get("unit", "unit"))[:20]
                    price = float(c.get("price", 0))
                    ch = c.get("change_24h")
                    comm_items.append(
                        CommodityIngestItem(
                            symbol=sym,
                            name=name,
                            commodity_type="metal" if sym in ("XAU", "XAG", "XPT", "XPD") else "energy",
                            price_usd=price,
                            unit=unit,
                            source="goldapi" if sym in ("XAU", "XAG", "XPT", "XPD") else "alpha_vantage",
                            change_24h_pct=float(ch) if ch is not None else None,
                        ),
                    )
                out["commodities"] = await self.persist_commodities(comm_items)
            except Exception as exc:
                logger.exception("ingest commodities: %s", exc)
                await _log_ingestion(
                    self.db,
                    endpoint="commodities",
                    status="error",
                    error_message=str(exc)[:2000],
                )
                await self.db.commit()

        return out

    async def ingest_commodities_only(self) -> int:
        """Commodity-only run for scheduled tasks (no forex/crypto)."""
        from app.modules.market_data.service import fetch_commodities

        try:
            comm_raw, _, _ = await fetch_commodities()
            comm_items: list[CommodityIngestItem] = []
            for c in comm_raw or []:
                sym = str(c.get("symbol", "UNK"))[:20]
                name = str(c.get("name", sym) or sym)[:100]
                unit = str(c.get("unit", "unit"))[:20]
                price = float(c.get("price", 0))
                ch = c.get("change_24h")
                src = "goldapi" if sym in ("XAU", "XAG", "XPT", "XPD") else "alpha_vantage"
                ctype = "metal" if sym in ("XAU", "XAG", "XPT", "XPD") else "energy"
                comm_items.append(
                    CommodityIngestItem(
                        symbol=sym,
                        name=name,
                        commodity_type=ctype,
                        price_usd=price,
                        unit=unit,
                        source=src,
                        change_24h_pct=float(ch) if ch is not None else None,
                    ),
                )
            return await self.persist_commodities(comm_items)
        except Exception as exc:
            logger.exception("ingest_commodities_only: %s", exc)
            await _log_ingestion(self.db, endpoint="commodities", status="error", error_message=str(exc)[:2000])
            await self.db.commit()
            return 0
