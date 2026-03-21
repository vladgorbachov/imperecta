"""Global product pool: listings joined to dim_product and dim_marketplace."""

from typing import Any
from uuid import UUID

from sqlalchemy import asc, desc, func, nullslast, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dimensions import DimMarketplace, DimProduct
from app.models.facts import FactListing, FactPrice

_SORT_RECENT = "recent"
_SORT_NAME_ASC = "name_asc"
_SORT_NAME_DESC = "name_desc"
_SORT_PRICE_ASC = "price_asc"
_SORT_PRICE_DESC = "price_desc"
_SORT_TRENDING = "trending"
_SORT_GAINERS = "gainers"
_SORT_LOSERS = "losers"
_SORT_VOLATILE = "volatile"


def _latest_price_change_subquery():
    """Latest fact_price row per listing (for price_change_pct and sorting)."""
    rn = func.row_number().over(
        partition_by=FactPrice.listing_id,
        order_by=desc(FactPrice.date_id),
    ).label("rn")
    inner = (
        select(
            FactPrice.listing_id,
            FactPrice.price_change_pct,
            rn,
        )
    ).subquery()
    return (
        select(inner.c.listing_id, inner.c.price_change_pct).where(inner.c.rn == 1)
    ).subquery()


class ProductPoolService:
    """List and aggregate global pool rows from v2 star schema."""

    def __init__(self, db: AsyncSession):
        self.db = db

    def _base_listing_stmt(self, latest_pc):
        """Shared SELECT for pool listings with optional price-change join."""
        return (
            select(
                FactListing.id,
                DimProduct.id.label("product_id"),
                DimProduct.name.label("title"),
                DimProduct.image_url,
                FactListing.external_url.label("url"),
                DimMarketplace.name.label("marketplace_name"),
                DimMarketplace.domain.label("marketplace_domain"),
                DimMarketplace.marketplace_code,
                DimMarketplace.country_code,
                FactListing.last_price.label("price"),
                FactListing.last_currency_code.label("currency"),
                FactListing.last_price_eur.label("price_eur"),
                FactListing.last_in_stock.label("in_stock"),
                FactListing.last_checked_at,
                FactListing.is_active,
                latest_pc.c.price_change_pct.label("price_change_pct"),
            )
            .select_from(FactListing)
            .join(DimProduct, FactListing.product_id == DimProduct.id)
            .join(DimMarketplace, FactListing.marketplace_id == DimMarketplace.id)
            .outerjoin(latest_pc, latest_pc.c.listing_id == FactListing.id)
            .where(FactListing.is_active.is_(True))
        )

    def _apply_filters(
        self,
        stmt,
        *,
        search: str | None,
        marketplace_id: UUID | None,
        category: str | None,
    ):
        if search:
            like = f"%{search}%"
            stmt = stmt.where(DimProduct.name.ilike(like))
        if marketplace_id is not None:
            stmt = stmt.where(FactListing.marketplace_id == marketplace_id)
        if category:
            cat = f"%{category}%"
            stmt = stmt.where(
                or_(
                    DimMarketplace.domain.ilike(cat),
                    DimMarketplace.name.ilike(cat),
                    DimMarketplace.marketplace_code.ilike(cat),
                )
            )
        return stmt

    def _apply_sort(self, stmt, sort: str, latest_pc):
        """Apply ordering for pool list (uses latest price-change when relevant)."""
        pct = latest_pc.c.price_change_pct
        abs_pct = func.abs(pct)
        if sort == _SORT_NAME_ASC:
            return stmt.order_by(asc(DimProduct.name))
        if sort == _SORT_NAME_DESC:
            return stmt.order_by(desc(DimProduct.name))
        if sort == _SORT_PRICE_ASC:
            return stmt.order_by(nullslast(asc(FactListing.last_price)))
        if sort == _SORT_PRICE_DESC:
            return stmt.order_by(nullslast(desc(FactListing.last_price)))
        if sort == _SORT_GAINERS:
            return stmt.order_by(nullslast(desc(pct)))
        if sort == _SORT_LOSERS:
            return stmt.order_by(nullslast(asc(pct)))
        if sort in (_SORT_VOLATILE, "volatile"):
            return stmt.order_by(nullslast(desc(abs_pct)))
        if sort in (_SORT_TRENDING, "trending"):
            return stmt.order_by(nullslast(desc(FactListing.last_checked_at)))
        # recent and unknown
        return stmt.order_by(nullslast(desc(FactListing.last_checked_at)))

    async def list_products(
        self,
        *,
        sort: str = "recent",
        search: str | None = None,
        marketplace_id: UUID | None = None,
        category: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        latest_pc = _latest_price_change_subquery()
        stmt = self._base_listing_stmt(latest_pc)
        stmt = self._apply_filters(stmt, search=search, marketplace_id=marketplace_id, category=category)
        stmt = self._apply_sort(stmt, sort, latest_pc)
        stmt = stmt.limit(limit).offset(offset)

        count_base = (
            select(func.count())
            .select_from(FactListing)
            .join(DimProduct, FactListing.product_id == DimProduct.id)
            .join(DimMarketplace, FactListing.marketplace_id == DimMarketplace.id)
            .where(FactListing.is_active.is_(True))
        )
        count_base = self._apply_filters(
            count_base,
            search=search,
            marketplace_id=marketplace_id,
            category=category,
        )

        total = await self.db.scalar(count_base) or 0
        result = await self.db.execute(stmt)
        rows = result.mappings().all()
        items = [_row_to_pool_item(dict(r)) for r in rows]
        return items, int(total)

    async def get_categories(self) -> list[dict]:
        """Distinct marketplaces that have active listings (lightweight category browse)."""
        stmt = (
            select(
                DimMarketplace.id,
                DimMarketplace.marketplace_code,
                DimMarketplace.name,
                DimMarketplace.domain,
                func.count(FactListing.id).label("listing_count"),
            )
            .select_from(FactListing)
            .join(DimMarketplace, FactListing.marketplace_id == DimMarketplace.id)
            .where(FactListing.is_active.is_(True))
            .group_by(
                DimMarketplace.id,
                DimMarketplace.marketplace_code,
                DimMarketplace.name,
                DimMarketplace.domain,
            )
            .order_by(desc("listing_count"))
        )
        result = await self.db.execute(stmt)
        return [
            {
                "marketplace_id": str(r.id),
                "marketplace_code": r.marketplace_code,
                "name": r.name,
                "domain": r.domain,
                "listing_count": int(r.listing_count),
            }
            for r in result.all()
        ]

    async def get_marketplace_stats(self) -> list[dict]:
        """Per-marketplace listing counts and average price (EUR) when available."""
        stmt = (
            select(
                DimMarketplace.id.label("marketplace_id"),
                DimMarketplace.name.label("marketplace_name"),
                DimMarketplace.domain.label("marketplace_domain"),
                DimMarketplace.country_code,
                func.count(FactListing.id).label("listing_count"),
                func.avg(FactListing.last_price_eur).label("avg_price_eur"),
            )
            .select_from(FactListing)
            .join(DimMarketplace, FactListing.marketplace_id == DimMarketplace.id)
            .where(FactListing.is_active.is_(True))
            .group_by(
                DimMarketplace.id,
                DimMarketplace.name,
                DimMarketplace.domain,
                DimMarketplace.country_code,
            )
            .order_by(desc("listing_count"))
        )
        result = await self.db.execute(stmt)
        out: list[dict] = []
        for r in result.all():
            avg = r.avg_price_eur
            out.append({
                "marketplace_domain": r.marketplace_domain,
                "marketplace_name": r.marketplace_name,
                "product_count": int(r.listing_count),
                "avg_price": float(avg) if avg is not None else None,
            })
        return out

    async def get_pool_stats(self) -> dict:
        """Aggregate counts for the global pool dashboard card."""
        total_listings = await self.db.scalar(
            select(func.count()).select_from(FactListing).where(FactListing.is_active.is_(True)),
        )
        total_products = await self.db.scalar(select(func.count()).select_from(DimProduct))
        marketplaces_count = await self.db.scalar(
            select(func.count()).select_from(DimMarketplace).where(DimMarketplace.is_active.is_(True)),
        )
        listings_with_price = await self.db.scalar(
            select(func.count())
            .select_from(FactListing)
            .where(FactListing.is_active.is_(True), FactListing.last_price.isnot(None)),
        )
        last_discovery = await self.db.scalar(select(func.max(DimMarketplace.last_discovery_at)))

        return {
            "total_products": int(total_products or 0),
            "total_listings": int(total_listings or 0),
            "marketplaces_count": int(marketplaces_count or 0),
            "listings_with_price": int(listings_with_price or 0),
            "last_updated": last_discovery,
            "total_marketplaces": int(marketplaces_count or 0),
            "products_with_price": int(listings_with_price or 0),
            "last_discovery_at": last_discovery,
            "message": None,
        }

    async def search_products(self, query: str, limit: int = 50) -> list[dict]:
        """Search pool by product title."""
        items, _total = await self.list_products(
            sort=_SORT_RECENT,
            search=query,
            limit=limit,
            offset=0,
        )
        return items


def _row_to_pool_item(row: dict[str, Any]) -> dict[str, Any]:
    """Normalize ORM row mapping to API dict (UUIDs as str for JSON)."""
    pct = row.get("price_change_pct")
    return {
        "id": row["id"],
        "product_id": row["product_id"],
        "title": row.get("title"),
        "image_url": row.get("image_url"),
        "url": row.get("url"),
        "marketplace_name": row.get("marketplace_name"),
        "marketplace_domain": row.get("marketplace_domain"),
        "marketplace_code": row.get("marketplace_code"),
        "country_code": row.get("country_code"),
        "price": float(row["price"]) if row.get("price") is not None else None,
        "currency": row.get("currency"),
        "price_eur": float(row["price_eur"]) if row.get("price_eur") is not None else None,
        "price_change_pct": float(pct) if pct is not None else None,
        "in_stock": row.get("in_stock"),
        "last_checked_at": row.get("last_checked_at"),
        "status": "active" if row.get("is_active") else "inactive",
        "is_active": row.get("is_active"),
    }
