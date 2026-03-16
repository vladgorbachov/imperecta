"""
Aggregate materialization for Markets page widgets.
Builds ticker bar, Market Overview, and lower analytics from stored snapshots.
Runs after raw ingestion. No provider calls.
"""

import logging
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AdminMarketplace,
    GlobalProduct,
    MarketsCategoryAnalytics,
    MarketsCommodity,
    MarketsCrypto,
    MarketsForex,
    MarketsMarketplaceAnalytics,
    MarketsOpportunityBlock,
    MarketsRefreshLog,
    MarketsRefreshStatus,
    MarketsRefreshType,
    MarketsTickerItem,
)

logger = logging.getLogger(__name__)

PROVIDER_FOREX = "frankfurter"
PROVIDER_CRYPTO = "coingecko"
PROVIDER_COMMODITIES = "http"
PROVIDER_FUEL = "fuel"
PROVIDER_AGGREGATE = "materialized"


class MarketDataAggregateService:
    """Materializes derived aggregates from stored forex, crypto, commodities."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def _log_start(self, refresh_type: MarketsRefreshType, provider: str) -> int:
        """Create refresh log entry. Returns log id."""
        entry = MarketsRefreshLog(
            refresh_type=refresh_type,
            status=MarketsRefreshStatus.running,
            provider_source=provider,
        )
        self.db.add(entry)
        await self.db.flush()
        return entry.id

    async def _log_success(self, log_id: int) -> None:
        """Mark refresh log as success."""
        from sqlalchemy import update

        from app.models import MarketsRefreshLog

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
        """Mark refresh log as error."""
        from sqlalchemy import update

        from app.models import MarketsRefreshLog

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
        """Build ticker bar from forex + crypto + commodities. Returns count."""
        log_id = await self._log_start(MarketsRefreshType.ticker, PROVIDER_AGGREGATE)
        try:
            now = datetime.now(timezone.utc)
            items: list[dict] = []

            forex_result = await self.db.execute(
                select(MarketsForex).order_by(MarketsForex.refreshed_at.desc())
            )
            for r in forex_result.scalars().all():
                items.append({
                    "symbol": r.symbol,
                    "name": r.symbol,
                    "price": float(r.bid),
                    "change_24h": float(r.change_24h) if r.change_24h is not None else None,
                    "currency": "USD",
                })

            crypto_result = await self.db.execute(
                select(MarketsCrypto).order_by(MarketsCrypto.refreshed_at.desc())
            )
            for r in crypto_result.scalars().all():
                items.append({
                    "symbol": r.symbol,
                    "name": r.symbol,
                    "price": float(r.price),
                    "change_24h": float(r.change_24h) if r.change_24h is not None else None,
                    "currency": "USD",
                })

            commodity_result = await self.db.execute(
                select(MarketsCommodity).order_by(MarketsCommodity.refreshed_at.desc())
            )
            for r in commodity_result.scalars().all():
                items.append({
                    "symbol": r.symbol,
                    "name": r.name or r.symbol,
                    "price": float(r.price),
                    "change_24h": float(r.change_24h) if r.change_24h is not None else None,
                    "currency": r.unit or "USD",
                })

            if not items:
                await self._log_success(log_id)
                logger.info("Ticker materialization skipped: no source data (forex/crypto/commodities empty)")
                return 0

            await self.db.execute(delete(MarketsTickerItem))
            for it in items[:50]:
                stmt = insert(MarketsTickerItem).values(
                    symbol=it["symbol"],
                    name=it.get("name"),
                    price=Decimal(str(it["price"])),
                    change_24h=Decimal(str(it["change_24h"])) if it.get("change_24h") is not None else None,
                    currency=it.get("currency"),
                    refreshed_at=now,
                ).on_conflict_do_update(
                    index_elements=["symbol"],
                    set_={
                        "name": it.get("name"),
                        "price": Decimal(str(it["price"])),
                        "change_24h": Decimal(str(it["change_24h"])) if it.get("change_24h") is not None else None,
                        "currency": it.get("currency"),
                        "refreshed_at": now,
                    },
                )
                await self.db.execute(stmt)

            await self.db.flush()
            await self._log_success(log_id)
            logger.info("Materialized %d ticker items", len(items[:50]))
            return len(items[:50])
        except Exception as e:
            await self._log_error(log_id, str(e))
            logger.exception("Ticker materialization failed: %s", e)
            raise

    async def materialize_overview(self) -> int:
        """Overview now reads from global_products directly. Kept for compatibility."""
        log_id = await self._log_start(MarketsRefreshType.overview, PROVIDER_AGGREGATE)
        await self._log_success(log_id)
        logger.info("Overview materialization skipped: /api/markets/overview reads from global_products")
        return 0

    async def materialize_category_analytics(self) -> int:
        """Build category/segment analytics from global product pool."""
        log_id = await self._log_start(MarketsRefreshType.category, PROVIDER_AGGREGATE)
        try:
            now = datetime.now(timezone.utc)
            result = await self.db.execute(
                select(GlobalProduct, AdminMarketplace)
                .join(AdminMarketplace, GlobalProduct.marketplace_id == AdminMarketplace.id)
                .where(AdminMarketplace.is_active.is_(True))
            )
            rows = result.all()

            by_category: dict[str, list[GlobalProduct]] = {}
            for product, marketplace in rows:
                cat = marketplace.marketplace_id
                if cat not in by_category:
                    by_category[cat] = []
                by_category[cat].append(product)

            await self.db.execute(delete(MarketsCategoryAnalytics))
            for cat_id, items in by_category.items():
                changes = [
                    float(x.price_change_pct_24h)
                    for x in items
                    if x.price_change_pct_24h is not None
                ]
                avg_change = sum(changes) / len(changes) if changes else 0
                metrics = {
                    "item_count": len(items),
                    "avg_change_24h": round(avg_change, 2),
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
            count = len(by_category)
            logger.info("Materialized %d category analytics", count)
            return count
        except Exception as e:
            await self._log_error(log_id, str(e))
            logger.exception("Category analytics materialization failed: %s", e)
            raise

    async def materialize_marketplace_analytics(self) -> int:
        """Build marketplace analytics from global_products + AdminMarketplace."""
        log_id = await self._log_start(MarketsRefreshType.marketplace, PROVIDER_AGGREGATE)
        try:
            now = datetime.now(timezone.utc)

            pool_result = await self.db.execute(
                select(GlobalProduct, AdminMarketplace)
                .join(AdminMarketplace, GlobalProduct.marketplace_id == AdminMarketplace.id)
                .where(AdminMarketplace.is_active.is_(True))
            )
            pool_rows = pool_result.all()

            by_mp: dict[str, dict[str, object]] = {}
            for product, marketplace in pool_rows:
                mp_id = marketplace.marketplace_id
                if mp_id not in by_mp:
                    by_mp[mp_id] = {
                        "name": marketplace.name,
                        "items": [],
                    }
                items = by_mp[mp_id]["items"]
                if isinstance(items, list):
                    items.append(product)

            admin_result = await self.db.execute(
                select(AdminMarketplace).where(AdminMarketplace.is_active.is_(True))
            )
            for marketplace in admin_result.scalars().all():
                if marketplace.marketplace_id not in by_mp:
                    by_mp[marketplace.marketplace_id] = {
                        "name": marketplace.name,
                        "items": [],
                    }

            await self.db.execute(delete(MarketsMarketplaceAnalytics))
            for mp_id, payload in by_mp.items():
                name = str(payload.get("name") or mp_id)
                items = payload.get("items")
                if not isinstance(items, list):
                    items = []
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
                    marketplace_name=name[:100],
                    metrics=metrics,
                    refreshed_at=now,
                )
                await self.db.execute(stmt)

            await self.db.flush()
            await self._log_success(log_id)
            count = len(by_mp)
            logger.info("Materialized %d marketplace analytics", count)
            return count
        except Exception as e:
            await self._log_error(log_id, str(e))
            logger.exception("Marketplace analytics materialization failed: %s", e)
            raise

    async def materialize_opportunities(self) -> int:
        """Build opportunity blocks from global product pool."""
        log_id = await self._log_start(MarketsRefreshType.opportunities, PROVIDER_AGGREGATE)
        try:
            now = datetime.now(timezone.utc)
            result = await self.db.execute(
                select(GlobalProduct).where(GlobalProduct.status == "active")
            )
            rows = result.scalars().unique().all()

            gainers = [r for r in rows if (r.price_change_pct_24h or 0) > 0]
            losers = [r for r in rows if (r.price_change_pct_24h or 0) < 0]
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
            logger.info("Materialized %d opportunity blocks", len(blocks))
            return len(blocks)
        except Exception as e:
            await self._log_error(log_id, str(e))
            logger.exception("Opportunities materialization failed: %s", e)
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
            except Exception as e:
                logger.error("Materialization %s failed: %s", name, e, exc_info=True)
                result[name] = 0
        return result
