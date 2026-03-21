"""
Dashboard aggregation service (v2 facts + user scope).
"""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.core import UserProduct
from app.models.dimensions import DimMarketplace
from app.models.facts import FactListing


class DashboardService:
    """KPI and trends; listing counts use global v2 facts."""

    def __init__(self, db: AsyncSession, user_id: UUID):
        self.db = db
        self.user_id = user_id

    async def get_kpi(self) -> dict:
        user_product_count = await self.db.scalar(
            select(func.count()).select_from(UserProduct).where(UserProduct.user_id == self.user_id),
        )
        listing_count = await self.db.scalar(
            select(func.count()).select_from(FactListing).where(FactListing.is_active.is_(True)),
        )
        marketplace_count = await self.db.scalar(
            select(func.count()).select_from(DimMarketplace).where(DimMarketplace.is_active.is_(True)),
        )
        return {
            "total_products": user_product_count or 0,
            "total_listings": listing_count or 0,
            "total_marketplaces": marketplace_count or 0,
            "total_competitors": 0,
            "total_competitor_products": 0,
            "avg_price_change_24h": 0.0,
            "active_alerts_count": 0,
            "critical_alerts_count": 0,
            "revenue_impact_percent": 0.0,
            "revenue_impact_confidence": 0.0,
            "products_at_risk": 0,
            "trend_vs_last_week": {"products": 0.0, "price_change": 0.0, "alerts": 0.0},
            "message": None,
        }

    async def get_anomalies(self, limit: int = 10) -> list[dict]:
        _ = limit
        return []

    async def get_aggregate_trend(self, period_days: int = 30, forecast_days: int = 7) -> dict:
        _ = period_days, forecast_days
        return {
            "labels": [],
            "my_products_avg": [],
            "competitors_avg": [],
            "forecast": [],
            "forecast_labels": [],
            "message": None,
        }
