"""Markets domain service. Reads from markets tables. Supports 2-hour scheduled refresh."""

import logging
import random
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    MarketsCategoryAnalytics,
    MarketsCommodity,
    MarketsCrypto,
    MarketsForex,
    MarketsMarketplaceAnalytics,
    MarketsOpportunityBlock,
    MarketsOverviewItem,
    MarketsPreferences,
    MarketsRefreshLog,
    MarketsRefreshStatus,
    MarketsRefreshType,
    MarketsTickerItem,
)

logger = logging.getLogger(__name__)


class MarketsService:
    """Service for markets data. Uses typed schemas."""

    def __init__(self, db: AsyncSession, user_id: UUID):
        self.db = db
        self.user_id = user_id

    async def get_preferences(self) -> dict:
        """Get or create user markets preferences."""
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
        """Update user markets preferences."""
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
        """Get refresh status: last_success, last_failed, provider, country_scope per type."""
        result = await self.db.execute(
            select(MarketsRefreshLog).order_by(MarketsRefreshLog.started_at.desc())
        )
        rows = result.scalars().all()

        last_success: dict[str, datetime | None] = {}
        last_failed: dict[str, datetime | None] = {}
        provider: dict[str, str | None] = {}
        country_scope: dict[str, str | None] = {}
        error_message: dict[str, str | None] = {}

        for r in rows:
            t = r.refresh_type.value
            if t not in last_success:
                last_success[t] = r.completed_at if r.status == MarketsRefreshStatus.success else None
            if t not in last_failed and r.status == MarketsRefreshStatus.error:
                last_failed[t] = r.completed_at
            if t not in provider:
                provider[t] = getattr(r, "provider_source", None)
            if t not in country_scope:
                country_scope[t] = getattr(r, "country_scope", None)
            if t not in error_message and r.error_message:
                error_message[t] = r.error_message

        types_seen = set(last_success.keys()) | set(last_failed.keys())
        return [
            {
                "refresh_type": t,
                "last_successful_refresh": last_success.get(t),
                "last_failed_refresh": last_failed.get(t),
                "provider_source": provider.get(t),
                "country_scope": country_scope.get(t),
                "error_message": error_message.get(t),
            }
            for t in sorted(types_seen)
        ]

    async def get_forex(self) -> dict:
        """Forex widget data."""
        result = await self.db.execute(
            select(MarketsForex).order_by(MarketsForex.refreshed_at.desc())
        )
        rows = result.scalars().unique().all()
        last_at = rows[0].refreshed_at if rows else None
        if not rows:
            logger.debug("get_forex: no rows in markets_forex")
        return {
            "items": [
                {
                    "symbol": r.symbol,
                    "bid": float(r.bid),
                    "ask": float(r.ask),
                    "spread": float(r.spread),
                    "change_24h": float(r.change_24h) if r.change_24h is not None else None,
                    "refreshed_at": r.refreshed_at,
                }
                for r in rows
            ],
            "last_refreshed_at": last_at,
        }

    async def get_crypto(self) -> dict:
        """Crypto widget data."""
        result = await self.db.execute(
            select(MarketsCrypto).order_by(MarketsCrypto.refreshed_at.desc())
        )
        rows = result.scalars().unique().all()
        last_at = rows[0].refreshed_at if rows else None
        if not rows:
            logger.debug("get_crypto: no rows in markets_crypto")
        return {
            "items": [
                {
                    "symbol": r.symbol,
                    "price": float(r.price),
                    "change_24h": float(r.change_24h) if r.change_24h is not None else None,
                    "market_cap": float(r.market_cap) if r.market_cap is not None else None,
                    "refreshed_at": r.refreshed_at,
                }
                for r in rows
            ],
            "last_refreshed_at": last_at,
        }

    async def get_commodities(self) -> dict:
        """Resources/commodities widget data."""
        result = await self.db.execute(
            select(MarketsCommodity).order_by(MarketsCommodity.refreshed_at.desc())
        )
        rows = result.scalars().unique().all()
        last_at = rows[0].refreshed_at if rows else None
        return {
            "items": [
                {
                    "symbol": r.symbol,
                    "name": r.name,
                    "price": float(r.price),
                    "change_24h": float(r.change_24h) if r.change_24h is not None else None,
                    "unit": r.unit,
                    "refreshed_at": r.refreshed_at,
                }
                for r in rows
            ],
            "last_refreshed_at": last_at,
        }

    async def get_ticker(self) -> dict:
        """Ticker bar data."""
        result = await self.db.execute(
            select(MarketsTickerItem).order_by(MarketsTickerItem.refreshed_at.desc())
        )
        rows = result.scalars().unique().all()
        last_at = rows[0].refreshed_at if rows else None
        return {
            "items": [
                {
                    "symbol": r.symbol,
                    "name": r.name,
                    "price": float(r.price),
                    "change_24h": float(r.change_24h) if r.change_24h is not None else None,
                    "currency": r.currency,
                    "refreshed_at": r.refreshed_at,
                }
                for r in rows
            ],
            "last_refreshed_at": last_at,
        }

    async def get_overview(self, sort: str = "volatile", limit: int = 50) -> dict:
        """
        Market Overview: global materialized rows from markets_overview.
        Data is produced by scheduled ingestion/materialization pipeline and is
        independent from user products/competitors.
        """
        result = await self.db.execute(
            select(MarketsOverviewItem).order_by(MarketsOverviewItem.refreshed_at.desc())
        )
        rows = result.scalars().all()

        if not rows:
            return {"items": [], "total": 0, "sort": sort, "last_refreshed_at": None}

        items: list[dict] = []
        for r in rows:
            marketplace_id = r.marketplace
            marketplace_label = marketplace_id.replace("_", " ").title()
            items.append({
                "id": str(r.id),
                "marketplace": marketplace_label,
                "marketplace_domain": r.marketplace_domain or "",
                "marketplace_id": marketplace_id,
                "product_name": (r.product_name or "Unknown")[:500],
                "product_url": None,
                "price": float(r.price),
                "currency": (r.currency or "USD"),
                "category": marketplace_id,
                "change_24h": float(r.change_24h) if r.change_24h is not None else None,
                "change_3d": float(r.change_3d) if r.change_3d is not None else None,
                "change_1w": float(r.change_1w) if r.change_1w is not None else None,
                "change_1m": float(r.change_1m) if r.change_1m is not None else None,
                "sparkline_data": r.sparkline_data if len(r.sparkline_data or []) >= 2 else [],
                "last_updated": r.refreshed_at,
            })

        # Random sample of marketplace products so overview shows varied items; sort/filter still apply
        total = len(items)
        if len(items) > limit:
            items = random.sample(items, limit)

        def _tie_key(x: dict) -> str:
            return f"{x['marketplace']}_{x['product_name']}"

        if sort == "volatile":
            items.sort(
                key=lambda x: (
                    -max(abs(x["change_24h"] or 0), abs(x["change_3d"] or 0)),
                    _tie_key(x),
                ),
            )
        elif sort == "trending":
            items.sort(key=lambda x: (-abs(x["change_24h"] or 0), _tie_key(x)))
        elif sort == "gainers":
            items = [x for x in items if (x["change_24h"] or 0) > 0]
            items.sort(key=lambda x: (-(x["change_24h"] or 0), _tie_key(x)))
        elif sort == "losers":
            items = [x for x in items if (x["change_24h"] or 0) < 0]
            items.sort(key=lambda x: ((x["change_24h"] or 0), _tie_key(x)))
        elif sort == "recent":
            items.sort(
                key=lambda x: (
                    -(x["last_updated"].timestamp() if x["last_updated"] else 0),
                    _tie_key(x),
                ),
            )
        else:
            items.sort(
                key=lambda x: (
                    -max(abs(x["change_24h"] or 0), abs(x["change_3d"] or 0)),
                    _tie_key(x),
                ),
            )
        last_at = items[0]["last_updated"] if items else None
        return {
            "items": items,
            "total": total,
            "sort": sort,
            "last_refreshed_at": last_at,
        }

    _NON_MARKETPLACE_IDS = frozenset({"crypto", "commodities", "forex"})

    async def get_category_analytics(self) -> dict:
        """Category/segment analytics data. Excludes crypto, commodities, forex (product-only)."""
        result = await self.db.execute(
            select(MarketsCategoryAnalytics).order_by(
                MarketsCategoryAnalytics.refreshed_at.desc()
            )
        )
        rows = result.scalars().unique().all()
        last_at = rows[0].refreshed_at if rows else None
        items = [
            {
                "id": str(r.id),
                "category_id": r.category_id,
                "segment": r.segment,
                "metrics": r.metrics or {},
                "refreshed_at": r.refreshed_at,
            }
            for r in rows
            if (r.category_id or "").lower() not in self._NON_MARKETPLACE_IDS
        ]
        return {
            "items": items,
            "last_refreshed_at": last_at,
        }

    async def get_marketplace_analytics(self) -> dict:
        """Marketplace table analytics. Excludes crypto, commodities, forex (marketplaces only)."""
        result = await self.db.execute(
            select(MarketsMarketplaceAnalytics).order_by(
                MarketsMarketplaceAnalytics.refreshed_at.desc()
            )
        )
        rows = result.scalars().unique().all()
        last_at = rows[0].refreshed_at if rows else None
        items = [
            {
                "id": str(r.id),
                "marketplace_id": r.marketplace_id,
                "marketplace_name": r.marketplace_name,
                "metrics": r.metrics or {},
                "refreshed_at": r.refreshed_at,
            }
            for r in rows
            if (r.marketplace_id or "").lower() not in self._NON_MARKETPLACE_IDS
        ]
        # Sort by product count DESC, then name ASC
        items.sort(
            key=lambda x: (
                -(x["metrics"].get("item_count") or 0),
                (x["marketplace_name"] or "").lower(),
            )
        )
        return {
            "items": items,
            "last_refreshed_at": last_at,
        }

    async def get_opportunities(self) -> dict:
        """Opportunity blocks data."""
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
                    "id": str(r.id),
                    "block_type": r.block_type,
                    "title": r.title,
                    "metrics": r.metrics or {},
                    "refreshed_at": r.refreshed_at,
                }
                for r in rows
            ],
            "last_refreshed_at": last_at,
        }
