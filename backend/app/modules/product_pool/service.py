"""
Read-only service for the global product pool.
Used by Dashboard/Market Overview and public-facing API.
"""

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.marketplaces.models import AdminMarketplace
from app.modules.product_pool.models import GlobalProduct


class ProductPoolService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_products(
        self,
        sort: str = "recent",
        search: str | None = None,
        marketplace_id: int | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict], int]:
        stmt = (
            select(GlobalProduct, AdminMarketplace.name, AdminMarketplace.domain)
            .join(AdminMarketplace, AdminMarketplace.id == GlobalProduct.marketplace_id)
            .where(GlobalProduct.status.in_(("active", "pending")))
        )

        if marketplace_id is not None:
            stmt = stmt.where(GlobalProduct.marketplace_id == marketplace_id)
        if search:
            stmt = stmt.where(GlobalProduct.title.ilike(f"%{search}%"))

        if sort in {"trending", "gainers", "losers", "volatile"}:
            stmt = stmt.where(GlobalProduct.current_price.is_not(None))

        count_stmt = (
            select(func.count())
            .select_from(GlobalProduct)
            .join(AdminMarketplace, AdminMarketplace.id == GlobalProduct.marketplace_id)
            .where(GlobalProduct.status.in_(("active", "pending")))
        )
        if marketplace_id is not None:
            count_stmt = count_stmt.where(GlobalProduct.marketplace_id == marketplace_id)
        if search:
            count_stmt = count_stmt.where(GlobalProduct.title.ilike(f"%{search}%"))
        if sort in {"trending", "gainers", "losers", "volatile"}:
            count_stmt = count_stmt.where(GlobalProduct.current_price.is_not(None))

        total = int(await self.db.scalar(count_stmt) or 0)

        if sort == "recent":
            stmt = stmt.order_by(GlobalProduct.discovered_at.desc().nullslast())
        elif sort == "trending":
            stmt = stmt.order_by(func.abs(GlobalProduct.price_change_pct_24h).desc().nullslast())
        elif sort == "gainers":
            stmt = stmt.order_by(GlobalProduct.price_change_pct_24h.desc().nullslast())
        elif sort == "losers":
            stmt = stmt.order_by(GlobalProduct.price_change_pct_24h.asc().nullslast())
        elif sort == "volatile":
            stmt = stmt.order_by(GlobalProduct.volatility_30d.desc().nullslast())
        else:
            stmt = stmt.order_by(GlobalProduct.discovered_at.desc().nullslast())

        stmt = stmt.limit(limit).offset(offset)
        rows = (await self.db.execute(stmt)).all()

        items: list[dict] = []
        for product, marketplace_name, marketplace_domain in rows:
            items.append(
                {
                    "id": product.id,
                    "marketplace_id": product.marketplace_id,
                    "marketplace_name": marketplace_name,
                    "marketplace_domain": marketplace_domain,
                    "url": product.url,
                    "title": product.title,
                    "image_url": product.image_url,
                    "description": product.description,
                    "current_price": float(product.current_price)
                    if product.current_price is not None
                    else None,
                    "original_price": float(product.original_price)
                    if product.original_price is not None
                    else None,
                    "currency": product.currency or "USD",
                    "price_change_pct_24h": float(product.price_change_pct_24h)
                    if product.price_change_pct_24h is not None
                    else None,
                    "price_change_pct_7d": float(product.price_change_pct_7d)
                    if product.price_change_pct_7d is not None
                    else None,
                    "price_change_pct_30d": float(product.price_change_pct_30d)
                    if product.price_change_pct_30d is not None
                    else None,
                    "volatility_30d": float(product.volatility_30d)
                    if product.volatility_30d is not None
                    else None,
                    "status": product.status,
                    "last_scraped_at": product.last_scraped_at,
                }
            )
        return items, total

    async def get_marketplace_stats(self) -> list[dict]:
        stmt = (
            select(
                AdminMarketplace.domain.label("marketplace_domain"),
                AdminMarketplace.name.label("marketplace_name"),
                func.count(GlobalProduct.id).label("product_count"),
                func.avg(GlobalProduct.current_price).label("avg_price"),
            )
            .join(GlobalProduct, GlobalProduct.marketplace_id == AdminMarketplace.id)
            .where(GlobalProduct.status.in_(("active", "pending")))
            .group_by(AdminMarketplace.id, AdminMarketplace.domain, AdminMarketplace.name)
            .order_by(func.count(GlobalProduct.id).desc())
        )
        rows = (await self.db.execute(stmt)).all()
        return [
            {
                "marketplace_domain": row.marketplace_domain,
                "marketplace_name": row.marketplace_name,
                "product_count": int(row.product_count or 0),
                "avg_price": float(row.avg_price) if row.avg_price is not None else None,
            }
            for row in rows
        ]

    async def get_pool_stats(self) -> dict:
        total_products = int(
            await self.db.scalar(
                select(func.count()).select_from(GlobalProduct).where(
                    GlobalProduct.status.in_(("active", "pending"))
                )
            )
            or 0
        )
        total_marketplaces = int(
            await self.db.scalar(
                select(func.count(func.distinct(GlobalProduct.marketplace_id))).where(
                    GlobalProduct.status.in_(("active", "pending"))
                )
            )
            or 0
        )
        products_with_price = int(
            await self.db.scalar(
                select(func.count()).select_from(GlobalProduct).where(
                    and_(
                        GlobalProduct.status.in_(("active", "pending")),
                        GlobalProduct.current_price.is_not(None),
                    )
                )
            )
            or 0
        )
        last_discovery_at = await self.db.scalar(select(func.max(AdminMarketplace.last_discovery_at)))
        return {
            "total_products": total_products,
            "total_marketplaces": total_marketplaces,
            "products_with_price": products_with_price,
            "last_discovery_at": last_discovery_at,
        }

    async def search_products(self, query: str, limit: int = 50) -> list[dict]:
        stmt = (
            select(GlobalProduct, AdminMarketplace.name, AdminMarketplace.domain)
            .join(AdminMarketplace, AdminMarketplace.id == GlobalProduct.marketplace_id)
            .where(GlobalProduct.status.in_(("active", "pending")))
            .where(GlobalProduct.title.ilike(f"%{query}%"))
            .order_by(GlobalProduct.discovered_at.desc().nullslast())
            .limit(limit)
        )
        rows = (await self.db.execute(stmt)).all()
        return [
            {
                "id": product.id,
                "marketplace_id": product.marketplace_id,
                "marketplace_name": marketplace_name,
                "marketplace_domain": marketplace_domain,
                "url": product.url,
                "title": product.title,
                "image_url": product.image_url,
                "current_price": float(product.current_price)
                if product.current_price is not None
                else None,
                "currency": product.currency or "USD",
                "status": product.status,
                "last_scraped_at": product.last_scraped_at,
            }
            for product, marketplace_name, marketplace_domain in rows
        ]
