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
    MarketsCategoryAnalytics,
    MarketsCommodity,
    MarketsCrypto,
    MarketsForex,
    MarketsMarketplaceAnalytics,
    MarketsOpportunityBlock,
    MarketsOverviewItem,
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
        """Build Market Overview from forex + crypto + commodities. Returns count."""
        log_id = await self._log_start(MarketsRefreshType.overview, PROVIDER_AGGREGATE)
        try:
            now = datetime.now(timezone.utc)
            items: list[dict] = []

            forex_result = await self.db.execute(
                select(MarketsForex).order_by(MarketsForex.refreshed_at.desc())
            )
            for r in forex_result.scalars().all():
                items.append({
                    "marketplace": "forex",
                    "marketplace_domain": "frankfurter.app",
                    "product_name": r.symbol,
                    "price": float(r.bid),
                    "currency": "USD",
                    "change_24h": float(r.change_24h) if r.change_24h is not None else None,
                    "change_3d": None,
                    "change_1w": None,
                    "change_1m": None,
                    "sparkline_data": [],
                })

            crypto_result = await self.db.execute(
                select(MarketsCrypto).order_by(MarketsCrypto.refreshed_at.desc())
            )
            for r in crypto_result.scalars().all():
                items.append({
                    "marketplace": "crypto",
                    "marketplace_domain": "coingecko.com",
                    "product_name": r.symbol,
                    "price": float(r.price),
                    "currency": "USD",
                    "change_24h": float(r.change_24h) if r.change_24h is not None else None,
                    "change_3d": None,
                    "change_1w": None,
                    "change_1m": None,
                    "sparkline_data": [],
                })

            commodity_result = await self.db.execute(
                select(MarketsCommodity).order_by(MarketsCommodity.refreshed_at.desc())
            )
            for r in commodity_result.scalars().all():
                items.append({
                    "marketplace": "commodities",
                    "marketplace_domain": "",
                    "product_name": r.name or r.symbol,
                    "price": float(r.price),
                    "currency": r.unit or "USD",
                    "change_24h": float(r.change_24h) if r.change_24h is not None else None,
                    "change_3d": None,
                    "change_1w": None,
                    "change_1m": None,
                    "sparkline_data": [],
                })

            if not items:
                await self._log_success(log_id)
                logger.info("Overview materialization skipped: no source data (forex/crypto/commodities empty)")
                return 0

            await self.db.execute(delete(MarketsOverviewItem))
            for it in items[:100]:
                stmt = insert(MarketsOverviewItem).values(
                    id=uuid4(),
                    marketplace=it["marketplace"],
                    marketplace_domain=it["marketplace_domain"],
                    product_name=it["product_name"][:500],
                    price=Decimal(str(it["price"])),
                    currency=it["currency"][:5],
                    change_24h=Decimal(str(it["change_24h"])) if it.get("change_24h") is not None else None,
                    change_3d=it.get("change_3d"),
                    change_1w=it.get("change_1w"),
                    change_1m=it.get("change_1m"),
                    sparkline_data=it.get("sparkline_data") or [],
                    refreshed_at=now,
                )
                await self.db.execute(stmt)

            await self.db.flush()
            await self._log_success(log_id)
            logger.info("Materialized %d overview items", len(items[:100]))
            return len(items[:100])
        except Exception as e:
            await self._log_error(log_id, str(e))
            logger.exception("Overview materialization failed: %s", e)
            raise

    async def materialize_category_analytics(self) -> int:
        """Build category/segment analytics from overview. Returns count."""
        log_id = await self._log_start(MarketsRefreshType.category, PROVIDER_AGGREGATE)
        try:
            now = datetime.now(timezone.utc)
            result = await self.db.execute(
                select(MarketsOverviewItem).order_by(MarketsOverviewItem.refreshed_at.desc())
            )
            rows = result.scalars().unique().all()

            by_category: dict[str, list] = {}
            for r in rows:
                cat = r.marketplace
                if cat not in by_category:
                    by_category[cat] = []
                by_category[cat].append(r)

            await self.db.execute(delete(MarketsCategoryAnalytics))
            for cat_id, items in by_category.items():
                changes = [float(x.change_24h) for x in items if x.change_24h is not None]
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
        """Build marketplace analytics from overview + AdminMarketplace. Returns count."""
        log_id = await self._log_start(MarketsRefreshType.marketplace, PROVIDER_AGGREGATE)
        try:
            now = datetime.now(timezone.utc)

            overview_result = await self.db.execute(
                select(MarketsOverviewItem).order_by(MarketsOverviewItem.refreshed_at.desc())
            )
            overview_rows = overview_result.scalars().unique().all()

            admin_result = await self.db.execute(
                select(AdminMarketplace.marketplace_id, AdminMarketplace.name).where(
                    AdminMarketplace.is_active.is_(True)
                )
            )
            admin_marketplaces = {r.marketplace_id: r.name for r in admin_result.all()}

            all_marketplaces = dict(admin_marketplaces)

            by_mp: dict[str, list] = {}
            for mp_id in all_marketplaces:
                by_mp[mp_id] = []
            for r in overview_rows:
                mp_id = r.marketplace
                if mp_id not in all_marketplaces:
                    all_marketplaces[mp_id] = mp_id.replace("_", " ").title()
                    by_mp[mp_id] = []
                by_mp[mp_id].append(r)

            await self.db.execute(delete(MarketsMarketplaceAnalytics))
            for mp_id, items in by_mp.items():
                name = all_marketplaces.get(mp_id, mp_id)
                changes = [float(x.change_24h) for x in items if x.change_24h is not None]
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
        """Build opportunity blocks from overview. Returns count."""
        log_id = await self._log_start(MarketsRefreshType.opportunities, PROVIDER_AGGREGATE)
        try:
            now = datetime.now(timezone.utc)
            result = await self.db.execute(
                select(MarketsOverviewItem).order_by(MarketsOverviewItem.refreshed_at.desc())
            )
            rows = result.scalars().unique().all()

            gainers = [r for r in rows if (r.change_24h or 0) > 0]
            losers = [r for r in rows if (r.change_24h or 0) < 0]
            gainers.sort(key=lambda x: x.change_24h or 0, reverse=True)
            losers.sort(key=lambda x: x.change_24h or 0)

            await self.db.execute(delete(MarketsOpportunityBlock))

            blocks = [
                (
                    "price_gains",
                    "Largest price gains",
                    {"count": len(gainers), "top_symbols": [r.product_name[:50] for r in gainers[:5]]},
                ),
                (
                    "price_drops",
                    "Largest price drops",
                    {"count": len(losers), "top_symbols": [r.product_name[:50] for r in losers[:5]]},
                ),
                (
                    "volatility",
                    "Price volatility",
                    {"total_items": len(rows), "with_change": len([r for r in rows if r.change_24h])},
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
            ("overview", self.materialize_overview),
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
