"""Global product pool: listings joined to dim_product and dim_marketplace."""

from datetime import date, datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import and_, asc, case, desc, func, nullslast, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dimensions import DimBrand, DimCategory, DimDate, DimMarketplace, DimProduct
from app.models.facts import FactListing, FactPrice
from app.modules.currency import (
    DISPLAY_LOCAL,
    CurrencyConverter,
    compute_display_fields_for_marketplace,
)

_SORT_RECENT = "recent"
_SORT_NAME_ASC = "name_asc"
_SORT_NAME_DESC = "name_desc"
_SORT_PRICE_ASC = "price_asc"
_SORT_PRICE_DESC = "price_desc"
_SORT_TRENDING = "trending"
_SORT_GAINERS = "gainers"
_SORT_LOSERS = "losers"
_SORT_VOLATILE = "volatile"
BLOCKED_PUBLIC_COUNTRY_CODES = frozenset({"RU", "BY"})
SPARKLINE_POINTS_LIMIT = 14

_POOL_STATS_STMT = text(
    """
    SELECT total_products, total_listings, marketplaces_count,
           listings_with_price, last_updated
    FROM mv_pool_stats
    """
)


def _pool_product_visibility_filter():
    """Listings that are gated products or legacy rows with a scraped price."""
    return or_(
        FactListing.page_role == "product",
        and_(FactListing.page_role.is_(None), FactListing.last_price.isnot(None)),
    )


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
                DimMarketplace.id.label("marketplace_id"),
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
                FactListing.last_checked_at,
                FactListing.is_active,
                latest_pc.c.price_change_pct.label("price_change_pct"),
            )
            .select_from(FactListing)
            .join(DimProduct, FactListing.product_id == DimProduct.id)
            .join(DimMarketplace, FactListing.marketplace_id == DimMarketplace.id)
            .outerjoin(latest_pc, latest_pc.c.listing_id == FactListing.id)
            .where(FactListing.is_active.is_(True))
            .where(_pool_product_visibility_filter())
        )

    def _apply_filters(
        self,
        stmt,
        *,
        search: str | None,
        marketplace_id: UUID | None,
        category: str | None,
        country_code: str | None = None,
    ):
        if search:
            like = f"%{search}%"
            stmt = stmt.where(DimProduct.name.ilike(like))
        if marketplace_id is not None:
            stmt = stmt.where(FactListing.marketplace_id == marketplace_id)
        if country_code:
            stmt = stmt.where(
                DimMarketplace.country_code == country_code.strip().upper(),
            )
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

    @staticmethod
    def _apply_country_visibility_filter(stmt, *, include_blocked_countries: bool):
        if include_blocked_countries:
            return stmt
        return stmt.where(DimMarketplace.country_code.notin_(BLOCKED_PUBLIC_COUNTRY_CODES))

    async def list_products(
        self,
        *,
        sort: str = "recent",
        search: str | None = None,
        marketplace_id: UUID | None = None,
        category: str | None = None,
        country_code: str | None = None,
        limit: int = 20,
        offset: int = 0,
        include_blocked_countries: bool = False,
        display_currency: str = DISPLAY_LOCAL,
    ) -> tuple[list[dict[str, Any]], int]:
        latest_pc = _latest_price_change_subquery()
        stmt = self._base_listing_stmt(latest_pc)
        stmt = self._apply_filters(
            stmt,
            search=search,
            marketplace_id=marketplace_id,
            category=category,
            country_code=country_code,
        )
        stmt = self._apply_country_visibility_filter(
            stmt,
            include_blocked_countries=include_blocked_countries,
        )
        stmt = self._apply_sort(stmt, sort, latest_pc)
        stmt = stmt.limit(limit).offset(offset)

        count_base = (
            select(func.count())
            .select_from(FactListing)
            .join(DimProduct, FactListing.product_id == DimProduct.id)
            .join(DimMarketplace, FactListing.marketplace_id == DimMarketplace.id)
            .where(FactListing.is_active.is_(True))
            .where(_pool_product_visibility_filter())
        )
        count_base = self._apply_filters(
            count_base,
            search=search,
            marketplace_id=marketplace_id,
            category=category,
            country_code=country_code,
        )
        count_base = self._apply_country_visibility_filter(
            count_base,
            include_blocked_countries=include_blocked_countries,
        )

        total = await self.db.scalar(count_base) or 0
        result = await self.db.execute(stmt)
        rows = result.mappings().all()
        items = [_row_to_pool_item(dict(r)) for r in rows]
        listing_ids = [item["id"] for item in items]
        recent_prices_by_listing = await self._get_recent_prices_map(listing_ids)
        for item in items:
            item["recent_prices"] = recent_prices_by_listing.get(item["id"], [])
        await self._apply_display_currency(items, display_currency)
        return items, int(total)


    async def get_product_detail(
        self,
        listing_id: UUID,
        *,
        include_blocked_countries: bool = False,
        display_currency: str = DISPLAY_LOCAL,
    ) -> dict[str, Any] | None:
        """One PoolProductItem by listing id + taxonomy labels; None when hidden.

        Same visibility rules as the list (active gated product + blocked-country
        filter), so a hidden/blocked listing is indistinguishable from absent.
        """
        latest_pc = _latest_price_change_subquery()
        stmt = self._base_listing_stmt(latest_pc).where(FactListing.id == listing_id)
        stmt = stmt.add_columns(
            DimProduct.attributes.label("attributes"),
            DimBrand.name.label("brand"),
            DimCategory.name.label("category"),
        )
        stmt = stmt.outerjoin(DimBrand, DimProduct.brand_id == DimBrand.id)
        stmt = stmt.outerjoin(DimCategory, DimProduct.category_id == DimCategory.id)
        stmt = self._apply_country_visibility_filter(
            stmt,
            include_blocked_countries=include_blocked_countries,
        )
        row = (await self.db.execute(stmt)).mappings().first()
        if row is None:
            return None
        raw = dict(row)
        attributes = raw.pop("attributes", None)
        brand = raw.pop("brand", None)
        category = raw.pop("category", None)
        item = _row_to_pool_item(raw)
        prices_map = await self._get_recent_prices_map([item["id"]])
        item["recent_prices"] = prices_map.get(item["id"], [])
        await self._apply_display_currency([item], display_currency)
        item["attributes"] = attributes if isinstance(attributes, dict) and attributes else None
        item["description"] = (
            attributes.get("description") if isinstance(attributes, dict) else None
        )
        item["brand"] = brand
        item["category"] = category
        return item

    async def get_price_history(
        self,
        listing_id: UUID,
        *,
        period: str = "30d",
        include_blocked_countries: bool = False,
    ) -> dict[str, Any] | None:
        """Daily price series for one listing; None when the listing is hidden.

        Latest scrape per day wins (same dedupe as visualisation_calc/trend);
        native price and price_eur both returned; data_ready needs >=2 days.
        """
        visible = await self.get_product_detail(
            listing_id,
            include_blocked_countries=include_blocked_countries,
        )
        if visible is None:
            return None

        days = {"7d": 7, "30d": 30, "90d": 90}.get(period, 30)
        today = datetime.now(timezone.utc).date()
        start = today - timedelta(days=days)
        min_date_id = start.year * 10_000 + start.month * 100 + start.day
        max_date_id = today.year * 10_000 + today.month * 100 + today.day

        ranked = (
            select(
                FactPrice.date_id,
                FactPrice.price,
                FactPrice.price_eur,
                FactPrice.currency_code,
                func.row_number()
                .over(
                    partition_by=[FactPrice.date_id],
                    order_by=desc(FactPrice.scraped_at),
                )
                .label("rn"),
            )
            .where(
                FactPrice.listing_id == listing_id,
                FactPrice.date_id >= min_date_id,
                FactPrice.date_id <= max_date_id,
            )
        ).subquery("ranked_prices")
        stmt = (
            select(ranked.c.date_id, ranked.c.price, ranked.c.price_eur, ranked.c.currency_code)
            .where(ranked.c.rn == 1)
            .order_by(ranked.c.date_id)
        )
        rows = (await self.db.execute(stmt)).all()
        points = [
            {
                "date": date(r.date_id // 10_000, r.date_id // 100 % 100, r.date_id % 100),
                "price": float(r.price) if r.price is not None else None,
                "price_eur": float(r.price_eur) if r.price_eur is not None else None,
            }
            for r in rows
        ]
        return {
            "listing_id": listing_id,
            "currency": visible.get("currency"),
            "period": period,
            "points": points if len(points) >= 2 else [],
            "data_ready": len(points) >= 2,
        }

    async def iter_export_rows(
        self,
        *,
        sort: str = "recent",
        search: str | None = None,
        marketplace_id: UUID | None = None,
        category: str | None = None,
        country_code: str | None = None,
        include_blocked_countries: bool = False,
        batch_size: int = 500,
    ):
        """Yield the FULL filtered pool (no pagination) for CSV export."""
        latest_pc = _latest_price_change_subquery()
        stmt = self._base_listing_stmt(latest_pc)
        stmt = self._apply_filters(
            stmt,
            search=search,
            marketplace_id=marketplace_id,
            category=category,
            country_code=country_code,
        )
        stmt = self._apply_country_visibility_filter(
            stmt,
            include_blocked_countries=include_blocked_countries,
        )
        stmt = self._apply_sort(stmt, sort, latest_pc)
        offset = 0
        while True:
            page = (
                (await self.db.execute(stmt.limit(batch_size).offset(offset)))
                .mappings()
                .all()
            )
            if not page:
                return
            for row in page:
                yield _row_to_pool_item(dict(row))
            if len(page) < batch_size:
                return
            offset += batch_size

    async def _apply_display_currency(
        self,
        items: list[dict[str, Any]],
        display_currency: str,
    ) -> None:
        """Populate display_price / display_currency / conversion_available /
        local_currency_resolution on items.

        For ``local`` mode the marketplace's local currency is resolved from
        the domain TLD (or country_code fallback); the parsed currency is
        converted into it when they differ. For ``EUR``/``USD`` the previous
        behaviour applies, plus the resolution metadata is still surfaced so
        the UI can disable the local-currency toggle when undeterminable.
        """
        if not items:
            return
        converter = await CurrencyConverter.load_latest(self.db)
        for item in items:
            fields = compute_display_fields_for_marketplace(
                amount=item.get("price"),
                currency=item.get("currency"),
                display_currency=display_currency,
                converter=converter,
                marketplace_domain=item.get("marketplace_domain"),
                marketplace_country_code=item.get("country_code"),
            )
            item.update(fields)

    async def _get_recent_prices_map(
        self,
        listing_ids: list[UUID],
        *,
        points_limit: int = SPARKLINE_POINTS_LIMIT,
    ) -> dict[UUID, list[dict[str, Any]]]:
        """Load recent price points for listings in one query."""
        if not listing_ids:
            return {}

        ranked = (
            select(
                FactPrice.listing_id.label("listing_id"),
                DimDate.full_date.label("full_date"),
                FactPrice.price.label("price"),
                FactPrice.currency_code.label("currency_code"),
                func.row_number().over(
                    partition_by=FactPrice.listing_id,
                    order_by=desc(FactPrice.date_id),
                ).label("row_num"),
            )
            .select_from(FactPrice)
            .join(DimDate, DimDate.date_id == FactPrice.date_id)
            .where(FactPrice.listing_id.in_(listing_ids))
        ).subquery()

        stmt = (
            select(
                ranked.c.listing_id,
                ranked.c.full_date,
                ranked.c.price,
                ranked.c.currency_code,
            )
            .where(ranked.c.row_num <= points_limit)
            .order_by(ranked.c.listing_id, ranked.c.full_date)
        )
        result = await self.db.execute(stmt)
        rows = result.all()

        output: dict[UUID, list[dict[str, Any]]] = {}
        for row in rows:
            output.setdefault(row.listing_id, []).append({
                "date": row.full_date.isoformat(),
                "price": float(row.price),
                "currency": row.currency_code,
            })
        return output

    async def get_categories(self, *, include_blocked_countries: bool = False) -> list[dict]:
        """Distinct marketplaces that have active listings (lightweight category browse)."""
        stmt = (
            select(
                DimMarketplace.id,
                DimMarketplace.marketplace_code,
                DimMarketplace.name,
                DimMarketplace.domain,
                DimMarketplace.country_code,
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
                DimMarketplace.country_code,
            )
            .order_by(desc("listing_count"))
        )
        stmt = self._apply_country_visibility_filter(
            stmt,
            include_blocked_countries=include_blocked_countries,
        )
        result = await self.db.execute(stmt)
        return [
            {
                "marketplace_id": str(r.id),
                "marketplace_code": r.marketplace_code,
                "name": r.name,
                "domain": r.domain,
                "country_code": r.country_code,
                "listing_count": int(r.listing_count),
            }
            for r in result.all()
        ]

    async def get_marketplace_stats(self, *, include_blocked_countries: bool = False) -> list[dict]:
        """Per-marketplace listing counts and average price (EUR) when available."""
        stmt = (
            select(
                DimMarketplace.id.label("marketplace_id"),
                DimMarketplace.name.label("marketplace_name"),
                DimMarketplace.domain.label("marketplace_domain"),
                DimMarketplace.country_code,
                func.sum(
                    case((FactListing.is_active.is_(True), 1), else_=0),
                ).label("listing_count"),
                func.avg(FactListing.last_price_eur).filter(FactListing.is_active.is_(True)).label("avg_price_eur"),
            )
            .select_from(DimMarketplace)
            .outerjoin(FactListing, FactListing.marketplace_id == DimMarketplace.id)
            .group_by(
                DimMarketplace.id,
                DimMarketplace.name,
                DimMarketplace.domain,
                DimMarketplace.country_code,
            )
            .where(DimMarketplace.is_active.is_(True))
            .order_by(desc("listing_count"), asc(DimMarketplace.name))
        )
        stmt = self._apply_country_visibility_filter(
            stmt,
            include_blocked_countries=include_blocked_countries,
        )
        result = await self.db.execute(stmt)
        out: list[dict] = []
        for r in result.all():
            avg = r.avg_price_eur
            out.append({
                "marketplace_domain": r.marketplace_domain,
                "marketplace_name": r.marketplace_name,
                "country_code": r.country_code,
                "product_count": int(r.listing_count),
                "avg_price": float(avg) if avg is not None else None,
            })
        return out

    async def get_pool_stats(self) -> dict:
        """Aggregate counts for the global pool dashboard card.

        Reads the single-row mv_pool_stats (refreshed by pg_cron every 10
        minutes, migration 051) instead of counting the 1.4M+ fact_listing
        rows per request — the live counts were hitting statement_timeout.
        """
        row = (await self.db.execute(_POOL_STATS_STMT)).mappings().first()
        if row is None:
            return {
                "total_products": 0,
                "total_listings": 0,
                "marketplaces_count": 0,
                "listings_with_price": 0,
                "last_updated": None,
            }
        return {
            "total_products": int(row["total_products"] or 0),
            "total_listings": int(row["total_listings"] or 0),
            "marketplaces_count": int(row["marketplaces_count"] or 0),
            "listings_with_price": int(row["listings_with_price"] or 0),
            "last_updated": row["last_updated"],
        }


def _row_to_pool_item(row: dict[str, Any]) -> dict[str, Any]:
    """Normalize ORM row mapping to API dict (UUIDs as str for JSON).

    Returns canonical-only fields. PP1 removed the legacy duplicate names
    (current_price, last_scraped_at, price_change_pct_24h) and the always-None
    placeholders (original_price, price_change_pct_7d/30d, volatility_30d):
    canonical readers are `price`, `last_checked_at`, `price_change_pct`.
    display_* / conversion_available / local_currency_* are populated later by
    `_apply_display_currency`; we seed them here so consumers can rely on the
    keys existing even when display currency resolution is skipped.
    """
    pct = row.get("price_change_pct")
    return {
        "id": row["id"],
        "marketplace_id": row.get("marketplace_id"),
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
        "display_price": None,
        "display_currency": None,
        "conversion_available": False,
        "local_currency_resolution": None,
        "local_currency_unavailable": False,
        "last_checked_at": row.get("last_checked_at"),
        "status": "active" if row.get("is_active") else "inactive",
        "is_active": row.get("is_active"),
        "recent_prices": [],
    }
