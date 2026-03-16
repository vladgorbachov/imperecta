"""Markets domain service. Reads from markets tables. Supports 2-hour scheduled refresh."""
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    MarketsCategoryAnalytics,
    MarketsMarketplaceAnalytics,
    MarketsOpportunityBlock,
    MarketsPreferences,
    MarketsRefreshLog,
    MarketsRefreshStatus,
)

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
