"""Markets domain service. Reads from markets tables. Supports 2-hour scheduled refresh."""

import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AdminMarketplace,
    Competitor,
    CompetitorProduct,
    MarketsCategoryAnalytics,
    MarketsCommodity,
    MarketsCrypto,
    MarketsForex,
    MarketsMarketplaceAnalytics,
    MarketsOpportunityBlock,
    MarketsPreferences,
    MarketsRefreshLog,
    MarketsRefreshStatus,
    MarketsRefreshType,
    MarketsTickerItem,
    PriceSnapshot,
    Product,
)

logger = logging.getLogger(__name__)

# Domain fallback for marketplace display. Extended from AdminMarketplace when available.
MARKETPLACE_DOMAIN: dict[str, str] = {}


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
        Market Overview: real scraped data from price_snapshots.
        Shows ALL competitor_products for the user with price changes.
        Only includes items that have at least one price snapshot.
        """
        now = datetime.now(timezone.utc)
        day_ago = now - timedelta(hours=24)
        three_days_ago = now - timedelta(days=3)
        week_ago = now - timedelta(days=7)
        month_ago = now - timedelta(days=30)

        cp_result = await self.db.execute(
            select(
                CompetitorProduct.id,
                CompetitorProduct.name.label("product_name"),
                CompetitorProduct.url,
                CompetitorProduct.last_price,
                CompetitorProduct.last_checked_at,
                Competitor.name.label("competitor_name"),
                Competitor.marketplace,
                Product.currency,
                Product.category,
            )
            .join(Competitor, CompetitorProduct.competitor_id == Competitor.id)
            .join(Product, CompetitorProduct.product_id == Product.id)
            .where(
                Competitor.user_id == self.user_id,
                CompetitorProduct.is_active.is_(True),
                CompetitorProduct.last_price.isnot(None),
                CompetitorProduct.last_price > 0,
            )
        )
        cp_rows = cp_result.all()

        if not cp_rows:
            return {"items": [], "total": 0, "sort": sort, "last_refreshed_at": None}

        cp_ids = [r.id for r in cp_rows]

        snap_result = await self.db.execute(
            select(
                PriceSnapshot.competitor_product_id,
                PriceSnapshot.price,
                PriceSnapshot.scraped_at,
            )
            .where(
                PriceSnapshot.competitor_product_id.in_(cp_ids),
                PriceSnapshot.scraped_at >= month_ago,
            )
            .order_by(PriceSnapshot.scraped_at.asc())
        )
        snapshots_raw = snap_result.all()

        snapshots_by_cp: dict[UUID, list[tuple[float, datetime]]] = {}
        for row in snapshots_raw:
            cp_id = row.competitor_product_id
            if cp_id not in snapshots_by_cp:
                snapshots_by_cp[cp_id] = []
            snapshots_by_cp[cp_id].append((float(row.price), row.scraped_at))

        admin_mp_result = await self.db.execute(
            select(AdminMarketplace.marketplace_id, AdminMarketplace.domain).where(
                AdminMarketplace.is_active.is_(True)
            )
        )
        domain_map = dict(MARKETPLACE_DOMAIN)
        for row in admin_mp_result.all():
            if row.domain:
                domain_map[row.marketplace_id] = row.domain

        items: list[dict] = []
        for r in cp_rows:
            snaps = snapshots_by_cp.get(r.id, [])
            if not snaps:
                continue

            current_price = float(r.last_price)
            prices_by_day: dict = {}
            for snap in snaps:
                day_key = snap[1].date()
                prices_by_day[day_key] = snap[0]

            def get_price_at(target_dt: datetime) -> float | None:
                target_date = target_dt.date()
                for i in range(3):
                    check_date = target_date - timedelta(days=i)
                    if check_date in prices_by_day:
                        return prices_by_day[check_date]
                return None

            def calc_change(old_p: float | None, new_p: float) -> float | None:
                if old_p and old_p > 0:
                    return round((new_p - old_p) / old_p * 100, 2)
                return None

            price_24h = get_price_at(day_ago)
            price_3d = get_price_at(three_days_ago)
            price_1w = get_price_at(week_ago)
            price_1m = get_price_at(month_ago)

            sparkline = list(prices_by_day.values())[-30:]
            domain = domain_map.get(r.marketplace, r.marketplace.replace("_", "."))
            last_updated = r.last_checked_at or (snaps[-1][1] if snaps else now)

            items.append({
                "id": str(r.id),
                "marketplace": r.competitor_name or r.marketplace,
                "marketplace_domain": domain,
                "marketplace_id": r.marketplace,
                "product_name": (r.product_name or "Unknown")[:500],
                "product_url": r.url or "",
                "price": current_price,
                "currency": (r.currency or "RUB"),
                "category": r.category,
                "change_24h": calc_change(price_24h, current_price),
                "change_3d": calc_change(price_3d, current_price),
                "change_1w": calc_change(price_1w, current_price),
                "change_1m": calc_change(price_1m, current_price),
                "sparkline_data": sparkline if len(sparkline) >= 2 else [],
                "last_updated": last_updated,
            })

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

        total = len(items)
        items = items[:limit]
        last_at = items[0]["last_updated"] if items else None
        return {
            "items": items,
            "total": total,
            "sort": sort,
            "last_refreshed_at": last_at,
        }

    async def get_category_analytics(self) -> dict:
        """Category/segment analytics data."""
        result = await self.db.execute(
            select(MarketsCategoryAnalytics).order_by(
                MarketsCategoryAnalytics.refreshed_at.desc()
            )
        )
        rows = result.scalars().unique().all()
        last_at = rows[0].refreshed_at if rows else None
        return {
            "items": [
                {
                    "id": str(r.id),
                    "category_id": r.category_id,
                    "segment": r.segment,
                    "metrics": r.metrics or {},
                    "refreshed_at": r.refreshed_at,
                }
                for r in rows
            ],
            "last_refreshed_at": last_at,
        }

    async def get_marketplace_analytics(self) -> dict:
        """Marketplace table analytics. Separate from competitor-benchmark."""
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
