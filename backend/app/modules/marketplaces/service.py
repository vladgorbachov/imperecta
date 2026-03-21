"""Marketplace pool: dim_marketplace quotas and discovery helpers."""

import logging
from urllib.parse import urlparse
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dimensions import DimMarketplace
from app.models.facts import FactListing

logger = logging.getLogger(__name__)


class MarketplacePoolService:
    """Maintain products_in_pool from fact_listing and expose dim_marketplace reads."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def recalculate_all_quotas(self) -> None:
        """Set products_in_pool to active listing counts per marketplace."""
        stmt = (
            select(FactListing.marketplace_id, func.count(FactListing.id))
            .where(FactListing.is_active.is_(True))
            .group_by(FactListing.marketplace_id)
        )
        result = await self.db.execute(stmt)
        rows = result.all()
        for marketplace_id, cnt in rows:
            await self.db.execute(
                update(DimMarketplace)
                .where(DimMarketplace.id == marketplace_id)
                .values(products_in_pool=int(cnt)),
            )
        await self.db.commit()
        logger.info("recalculate_all_quotas updated %d marketplaces", len(rows))

    async def list_active_marketplaces(self) -> list[DimMarketplace]:
        """All active rows from dim_marketplace (workers / admin)."""
        result = await self.db.execute(
            select(DimMarketplace)
            .where(DimMarketplace.is_active.is_(True))
            .order_by(DimMarketplace.marketplace_code),
        )
        return list(result.scalars().all())

    async def get_by_id(self, marketplace_id: UUID) -> DimMarketplace | None:
        """Load one marketplace by primary key."""
        result = await self.db.execute(select(DimMarketplace).where(DimMarketplace.id == marketplace_id))
        return result.scalar_one_or_none()

    async def get_by_code(self, marketplace_code: str) -> DimMarketplace | None:
        """Load marketplace by stable code (replaces legacy int marketplace_id)."""
        code = (marketplace_code or "").strip()
        if not code:
            return None
        result = await self.db.execute(
            select(DimMarketplace).where(DimMarketplace.marketplace_code == code),
        )
        return result.scalar_one_or_none()

    @staticmethod
    def _normalize_url(url: str) -> str:
        raw = (url or "").strip()
        if not raw:
            raise ValueError("URL is empty")
        if "://" not in raw:
            raw = f"https://{raw}"
        parsed = urlparse(raw)
        host = (parsed.netloc or parsed.path).lower().strip()
        if not host:
            raise ValueError("Invalid URL: could not extract domain")
        if "@" in host:
            host = host.split("@", 1)[1]
        host = host.split(":", 1)[0].strip("/")
        if host.startswith("www."):
            host = host[4:]
        if not host:
            raise ValueError("Invalid URL: could not extract domain")
        return f"https://{host}"
