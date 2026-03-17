"""
Aggregate materialization for Markets page widgets.
Builds ticker bar and lower analytics from stored snapshots.
"""

import logging
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    MarketsCategoryAnalytics,
    MarketsMarketplaceAnalytics,
    MarketsOpportunityBlock,
)
from app.modules.market_data.models import (
    MarketsCommodity,
    MarketsCrypto,
    MarketsForex,
    MarketsRefreshLog,
    MarketsRefreshStatus,
    MarketsRefreshType,
    MarketsTickerItem,
)
from app.modules.product_pool.models import GlobalProduct

logger = logging.getLogger(__name__)
PROVIDER_AGGREGATE = "materialized"


class MarketDataAggregateService:
    """Materializes derived aggregates from stored forex, crypto, commodities."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def _log_start(self, refresh_type: MarketsRefreshType, provider: str) -> int:
        entry = MarketsRefreshLog(
            refresh_type=refresh_type,
            status=MarketsRefreshStatus.running,
            provider_source=provider,
        )
        self.db.add(entry)
        await self.db.flush()
        return entry.id

    async def _log_success(self, log_id: int) -> None:
        from sqlalchemy import update

        await self.db.execute(
            update(MarketsRefreshLog)
            .where(MarketsRefreshLog.id == log_id)
            .values(
                status=MarketsRefreshStatus.success,
                completed_at=datetime.now(timezone.utc),
                error_message=None,
            )
        )
        await self.db.flush()

    async def _log_error(self, log_id: int, message: str) -> None:
        from sqlalchemy import update

        await self.db.execute(
            update(MarketsRefreshLog)
            .where(MarketsRefreshLog.id == log_id)
            .values(
                status=MarketsRefreshStatus.error,
                completed_at=datetime.now(timezone.utc),
                error_message=message,
            )
        )
        await self.db.flush()

    async def materialize_ticker(self) -> int:
        log_id = await self._log_start(MarketsRefreshType.ticker, PROVIDER_AGGREGATE)
        try:
            now = datetime.now(timezone.utc)
            items: list[dict] = []

            forex_result = await self.db.execute(select(MarketsForex).order_by(MarketsForex.refreshed_at.desc()))
            for row in forex_result.scalars().all():
                items.append({
                    "symbol": row.symbol,
                    "name": row.symbol,
                    "price": float(row.bid),
                    "change_24h": float(row.change_24h) if row.change_24h is not None else None,
                    "currency": "USD",
                })

            crypto_result = await self.db.execute(select(MarketsCrypto).order_by(MarketsCrypto.refreshed_at.desc()))
            for row in crypto_result.scalars().all():
                items.append({
                    "symbol": row.symbol,
                    "name": row.symbol,
                    "price": float(row.price),
                    "change_24h": float(row.change_24h) if row.change_24h is not None else None,
                    "currency": "USD",
                })

            commodity_result = await self.db.execute(select(MarketsCommodity).order_by(MarketsCommodity.refreshed_at.desc()))
            for row in commodity_result.scalars().all():
                items.append({
                    "symbol": row.symbol,
                    "name": row.name or row.symbol,
                    "price": float(row.price),
                    "change_24h": float(row.change_24h) if row.change_24h is not None else None,
                    "currency": row.unit or "USD",
                })

            if not items:
                await self._log_success(log_id)
                logger.info("Ticker materialization skipped: no source data")
                return 0

            await self.db.execute(delete(MarketsTickerItem))
            for item in items[:50]:
                stmt = insert(MarketsTickerItem).values(
                    symbol=item["symbol"],
                    name=item.get("name"),
                    price=Decimal(str(item["price"])),
                    change_24h=Decimal(str(item["change_24h"])) if item.get("change_24h") is not None else None,
                    currency=item.get("currency"),
                    refreshed_at=now,
                ).on_conflict_do_update(
                    index_elements=["symbol"],
                    set_={
                        "name": item.get("name"),
                        "price": Decimal(str(item["price"])),
                        "change_24h": Decimal(str(item["change_24h"])) if item.get("change_24h") is not None else None,
                        "currency": item.get("currency"),
                        "refreshed_at": now,
                    },
                )
                await self.db.execute(stmt)

            await self.db.flush()
            await self._log_success(log_id)
            logger.info("Materialized %d ticker items", len(items[:50]))
            return len(items[:50])
        except Exception as error:
            await self._log_error(log_id, str(error))
            logger.exception("Ticker materialization failed: %s", error)
            raise

    async def materialize_overview(self) -> int:
        log_id = await self._log_start(MarketsRefreshType.overview, PROVIDER_AGGREGATE)
        await self._log_success(log_id)
        logger.info("Overview materialization skipped: /api/markets/overview reads from global_products")
        return 0

    async def materialize_category_analytics(self) -> int:
        log_id = await self._log_start(MarketsRefreshType.category, PROVIDER_AGGREGATE)
        try:
            now = datetime.now(timezone.utc)
            result = await self.db.execute(select(GlobalProduct))
            rows = result.scalars().all()

            by_category: dict[str, list[GlobalProduct]] = {}
            for product in rows:
                cat = str(product.marketplace_id)
                by_category.setdefault(cat, []).append(product)

            await self.db.execute(delete(MarketsCategoryAnalytics))
            for cat_id, items in by_category.items():
                changes = [
                    float(x.price_change_pct_24h)
                    for x in items
                    if x.price_change_pct_24h is not None
                ]
                metrics = {
                    "item_count": len(items),
                    "avg_change_24h": round(sum(changes) / len(changes), 2) if changes else 0,
                    "max_change_24h": round(max(changes), 2) if changes else 0,
                    "min_change_24h": round(min(changes), 2) if changes else 0,
                }
                stmt = insert(MarketsCategoryAnalytics).values(
                    id=uuid4(),
                    category_id=cat_id[:100],
                    segment=None,
                    metrics=metrics,
                    refreshed_at=now,
                )
                await self.db.execute(stmt)

            await self.db.flush()
            await self._log_success(log_id)
            return len(by_category)
        except Exception as error:
            await self._log_error(log_id, str(error))
            logger.exception("Category analytics materialization failed: %s", error)
            raise

    async def materialize_marketplace_analytics(self) -> int:
        log_id = await self._log_start(MarketsRefreshType.marketplace, PROVIDER_AGGREGATE)
        try:
            now = datetime.now(timezone.utc)
            result = await self.db.execute(select(GlobalProduct))
            rows = result.scalars().all()

            by_mp: dict[str, list[GlobalProduct]] = {}
            for product in rows:
                key = str(product.marketplace_id)
                by_mp.setdefault(key, []).append(product)

            await self.db.execute(delete(MarketsMarketplaceAnalytics))
            for mp_id, items in by_mp.items():
                changes = [
                    float(x.price_change_pct_24h)
                    for x in items
                    if x.price_change_pct_24h is not None
                ]
                metrics = {
                    "item_count": len(items),
                    "avg_change_24h": round(sum(changes) / len(changes), 2) if changes else 0,
                }
                stmt = insert(MarketsMarketplaceAnalytics).values(
                    id=uuid4(),
                    marketplace_id=mp_id[:50],
                    marketplace_name=mp_id[:100],
                    metrics=metrics,
                    refreshed_at=now,
                )
                await self.db.execute(stmt)

            await self.db.flush()
            await self._log_success(log_id)
            return len(by_mp)
        except Exception as error:
            await self._log_error(log_id, str(error))
            logger.exception("Marketplace analytics materialization failed: %s", error)
            raise

    async def materialize_opportunities(self) -> int:
        log_id = await self._log_start(MarketsRefreshType.opportunities, PROVIDER_AGGREGATE)
        try:
            now = datetime.now(timezone.utc)
            result = await self.db.execute(
                select(GlobalProduct).where(GlobalProduct.status == "active")
            )
            rows = result.scalars().unique().all()

            gainers = [row for row in rows if (row.price_change_pct_24h or 0) > 0]
            losers = [row for row in rows if (row.price_change_pct_24h or 0) < 0]
            gainers.sort(key=lambda x: x.price_change_pct_24h or 0, reverse=True)
            losers.sort(key=lambda x: x.price_change_pct_24h or 0)

            await self.db.execute(delete(MarketsOpportunityBlock))
            blocks = [
                (
                    "price_gains",
                    "Largest price gains",
                    {
                        "count": len(gainers),
                        "top_symbols": [(r.title or "Unknown")[:50] for r in gainers[:5]],
                    },
                ),
                (
                    "price_drops",
                    "Largest price drops",
                    {
                        "count": len(losers),
                        "top_symbols": [(r.title or "Unknown")[:50] for r in losers[:5]],
                    },
                ),
                (
                    "volatility",
                    "Price volatility",
                    {
                        "total_items": len(rows),
                        "with_change": len([r for r in rows if r.price_change_pct_24h is not None]),
                    },
                ),
            ]
            for block_type, title, metrics in blocks:
                stmt = insert(MarketsOpportunityBlock).values(
                    id=uuid4(),
                    block_type=block_type[:50],
                    title=title[:255],
                    metrics=metrics,
                    refreshed_at=now,
                )
                await self.db.execute(stmt)

            await self.db.flush()
            await self._log_success(log_id)
            return len(blocks)
        except Exception as error:
            await self._log_error(log_id, str(error))
            logger.exception("Opportunities materialization failed: %s", error)
            raise

    async def materialize_all(self) -> dict[str, int]:
        """Run all aggregate materialization. Returns counts."""
        result = {}
        for name, fn in [
            ("ticker", self.materialize_ticker),
            ("category", self.materialize_category_analytics),
            ("marketplace", self.materialize_marketplace_analytics),
            ("opportunities", self.materialize_opportunities),
        ]:
            try:
                result[name] = await fn()
            except Exception as error:
                logger.error("Materialization %s failed: %s", name, error, exc_info=True)
                result[name] = 0
        return result
