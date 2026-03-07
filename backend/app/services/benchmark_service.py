"""Competitor benchmarking and scoring service."""

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Competitor, CompetitorProduct, PriceSnapshot, Product


class BenchmarkService:
    """Competitor benchmark scoring and comparison matrix."""

    def __init__(self, db: AsyncSession, user_id: UUID):
        self.db = db
        self.user_id = user_id

    async def get_competitor_scores(self) -> list[dict]:
        """
        Calculate Competitor Benchmark Score (0-100) for each competitor.

        Score components:
        - Price aggressiveness (0-40): how often and how deeply they undercut
        - Activity level (0-20): frequency of price changes
        - Promotion intensity (0-20): how often they run promos
        - Market coverage (0-20): how many products they sell in user's categories
        """
        now = datetime.now(timezone.utc)
        cutoff_30d = now - timedelta(days=30)

        # Get all competitors for user
        competitors_result = await self.db.execute(
            select(Competitor.id, Competitor.name, Competitor.marketplace).where(
                Competitor.user_id == self.user_id
            )
        )
        competitors = competitors_result.all()

        # Get user products with prices
        products_result = await self.db.execute(
            select(Product.id, Product.name, Product.current_price).where(
                Product.user_id == self.user_id,
                Product.is_active.is_(True),
            )
        )
        products = {p.id: p for p in products_result.all()}

        scores: list[dict] = []

        for comp_id, comp_name, marketplace in competitors:
            # Market coverage: count competitor_products
            coverage_result = await self.db.execute(
                select(func.count())
                .select_from(CompetitorProduct)
                .where(
                    CompetitorProduct.competitor_id == comp_id,
                    CompetitorProduct.is_active.is_(True),
                )
            )
            product_count = coverage_result.scalar() or 0
            market_coverage = min(20, product_count * 2)  # 10+ products = 20

            # Activity level: snapshot count in last 30 days
            activity_result = await self.db.execute(
                select(func.count())
                .select_from(PriceSnapshot)
                .join(CompetitorProduct, PriceSnapshot.competitor_product_id == CompetitorProduct.id)
                .where(
                    CompetitorProduct.competitor_id == comp_id,
                    PriceSnapshot.scraped_at >= cutoff_30d,
                )
            )
            snapshot_count = activity_result.scalar() or 0
            activity_level = min(20, snapshot_count // 4)  # 80+ snapshots = 20

            # Promotion intensity: promo ratio
            promo_result = await self.db.execute(
                select(func.count())
                .select_from(PriceSnapshot)
                .join(CompetitorProduct, PriceSnapshot.competitor_product_id == CompetitorProduct.id)
                .where(
                    CompetitorProduct.competitor_id == comp_id,
                    PriceSnapshot.scraped_at >= cutoff_30d,
                    PriceSnapshot.promo_label.isnot(None),
                    PriceSnapshot.promo_label != "",
                )
            )
            promo_count = promo_result.scalar() or 0
            promo_ratio = promo_count / snapshot_count if snapshot_count else 0
            promotion_intensity = int(min(20, promo_ratio * 40))

            # Price aggressiveness: undercut frequency and depth
            # Get competitor_product ids for this competitor
            cp_ids_result = await self.db.execute(
                select(CompetitorProduct.id, CompetitorProduct.product_id, CompetitorProduct.last_price)
                .where(
                    CompetitorProduct.competitor_id == comp_id,
                    CompetitorProduct.is_active.is_(True),
                )
            )
            cp_rows = cp_ids_result.all()

            undercut_count = 0
            undercut_depth_sum = 0.0
            price_ratios: list[float] = []

            for cp_id, prod_id, last_price in cp_rows:
                if prod_id not in products or not last_price:
                    continue
                my_price = float(products[prod_id].current_price)
                comp_price = float(last_price)
                price_ratios.append(comp_price / my_price * 100 if my_price else 0)

                if comp_price < my_price:
                    undercut_count += 1
                    depth = (my_price - comp_price) / my_price * 100
                    undercut_depth_sum += depth

            if cp_rows:
                price_index = sum(price_ratios) / len(price_ratios) if price_ratios else 100
            else:
                price_index = 100.0

            # Aggressiveness: more undercuts + deeper = higher score
            undercut_ratio = undercut_count / len(cp_rows) if cp_rows else 0
            avg_depth = undercut_depth_sum / undercut_count if undercut_count else 0
            price_aggressiveness = 0
            if undercut_count:
                price_aggressiveness = min(
                    40,
                    int(undercut_ratio * 20 + min(avg_depth / 5, 20)),
                )

            # Last change
            last_change_result = await self.db.execute(
                select(
                    PriceSnapshot.price,
                    PriceSnapshot.old_price,
                    PriceSnapshot.scraped_at,
                )
                .join(CompetitorProduct, PriceSnapshot.competitor_product_id == CompetitorProduct.id)
                .where(CompetitorProduct.competitor_id == comp_id)
                .order_by(PriceSnapshot.scraped_at.desc())
                .limit(2)
            )
            last_rows = last_change_result.all()
            last_change_pct = 0.0
            if len(last_rows) >= 2 and last_rows[1].old_price and float(last_rows[1].old_price) > 0:
                last_change_pct = (
                    (float(last_rows[0].price) - float(last_rows[1].price))
                    / float(last_rows[1].price)
                    * 100
                )
            elif len(last_rows) == 1 and last_rows[0].old_price and float(last_rows[0].old_price) > 0:
                last_change_pct = (
                    (float(last_rows[0].price) - float(last_rows[0].old_price))
                    / float(last_rows[0].old_price)
                    * 100
                )

            # Trend 30d: daily avg prices for sparkline
            date_col = func.date_trunc("day", PriceSnapshot.scraped_at)
            trend_result = await self.db.execute(
                select(date_col.label("dt"), func.avg(PriceSnapshot.price).label("avg_price"))
                .join(CompetitorProduct, PriceSnapshot.competitor_product_id == CompetitorProduct.id)
                .where(
                    CompetitorProduct.competitor_id == comp_id,
                    PriceSnapshot.scraped_at >= cutoff_30d,
                )
                .group_by(date_col)
                .order_by(date_col)
            )
            trend_rows = trend_result.all()
            trend_map = {r.dt.date() if hasattr(r.dt, "date") else r.dt: float(r.avg_price) for r in trend_rows}

            trend_30d: list[float] = []
            for i in range(30):
                d = (now - timedelta(days=29 - i)).date()
                trend_30d.append(trend_map.get(d, 0.0))

            # Total score
            total_score = sum([
                price_aggressiveness,
                activity_level,
                promotion_intensity,
                market_coverage,
            ])

            if total_score >= 60:
                aggressiveness = "aggressive"
            elif total_score >= 30:
                aggressiveness = "moderate"
            else:
                aggressiveness = "passive"

            scores.append({
                "competitor_id": str(comp_id),
                "competitor_name": comp_name,
                "marketplace": marketplace,
                "score": min(100, total_score),
                "aggressiveness": aggressiveness,
                "components": {
                    "price_aggressiveness": price_aggressiveness,
                    "activity_level": activity_level,
                    "promotion_intensity": promotion_intensity,
                    "market_coverage": market_coverage,
                },
                "price_index": round(price_index, 2),
                "last_change_pct": round(last_change_pct, 2),
                "trend_30d": [round(v, 2) for v in trend_30d],
            })

        return sorted(scores, key=lambda x: x["score"], reverse=True)

    async def get_comparison_matrix(self) -> dict:
        """
        Price comparison matrix: my products × competitors.
        matrix[product_idx][competitor_idx] = % difference (positive = I'm cheaper)
        """
        products_result = await self.db.execute(
            select(Product.id, Product.name, Product.current_price).where(
                Product.user_id == self.user_id,
                Product.is_active.is_(True),
            ).order_by(Product.name)
        )
        products = products_result.all()

        competitors_result = await self.db.execute(
            select(Competitor.id, Competitor.name, Competitor.marketplace).where(
                Competitor.user_id == self.user_id
            ).order_by(Competitor.name)
        )
        competitors = competitors_result.all()

        product_ids = [p.id for p in products]
        competitor_ids = [c.id for c in competitors]

        # Build map: (product_id, competitor_id) -> last_price
        cp_result = await self.db.execute(
            select(
                CompetitorProduct.product_id,
                CompetitorProduct.competitor_id,
                CompetitorProduct.last_price,
            ).where(
                CompetitorProduct.product_id.in_(product_ids),
                CompetitorProduct.competitor_id.in_(competitor_ids),
                CompetitorProduct.is_active.is_(True),
            )
        )
        price_map: dict[tuple[UUID, UUID], float] = {}
        for row in cp_result.all():
            if row.last_price:
                price_map[(row.product_id, row.competitor_id)] = float(row.last_price)

        matrix: list[list[float | None]] = []
        for product in products:
            row: list[float | None] = []
            my_price = float(product.current_price)
            for competitor in competitors:
                comp_price = price_map.get((product.id, competitor.id))
                if comp_price is None or my_price == 0:
                    row.append(None)
                else:
                    # % diff: positive = I'm cheaper (my_price < comp_price)
                    diff_pct = (my_price - comp_price) / comp_price * 100
                    row.append(round(diff_pct, 2))
            matrix.append(row)

        return {
            "products": [{"id": str(p.id), "name": p.name} for p in products],
            "competitors": [
                {"id": str(c.id), "name": c.name, "marketplace": c.marketplace}
                for c in competitors
            ],
            "matrix": matrix,
        }
