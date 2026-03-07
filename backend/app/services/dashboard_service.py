"""Dashboard aggregation service for KPIs and analytics."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Alert,
    AlertEvent,
    Competitor,
    CompetitorProduct,
    PriceSnapshot,
    Product,
    ScrapeLog,
)


class DashboardService:
    """Aggregation service for dashboard KPIs and analytics."""

    def __init__(self, db: AsyncSession, user_id: UUID):
        self.db = db
        self.user_id = user_id

    async def get_kpi(self) -> dict:
        """
        Returns dashboard KPIs.

        Returns:
            dict with total_products, total_competitors, total_competitor_products,
            avg_price_change_24h, active_alerts_count, critical_alerts_count,
            revenue_impact_percent, revenue_impact_confidence, products_at_risk,
            trend_vs_last_week.
        """
        now = datetime.now(timezone.utc)
        day_ago = now - timedelta(hours=24)
        week_ago = now - timedelta(days=7)
        two_weeks_ago = now - timedelta(days=14)

        # total_products: active products only
        total_products_result = await self.db.execute(
            select(func.count())
            .select_from(Product)
            .where(Product.user_id == self.user_id, Product.is_active.is_(True))
        )
        total_products = total_products_result.scalar() or 0

        # total_competitors
        total_competitors_result = await self.db.execute(
            select(func.count()).select_from(Competitor).where(Competitor.user_id == self.user_id)
        )
        total_competitors = total_competitors_result.scalar() or 0

        # total_competitor_products (active)
        total_cp_result = await self.db.execute(
            select(func.count())
            .select_from(CompetitorProduct)
            .join(Product, CompetitorProduct.product_id == Product.id)
            .where(Product.user_id == self.user_id, CompetitorProduct.is_active.is_(True))
        )
        total_competitor_products = total_cp_result.scalar() or 0

        # avg_price_change_24h: for each competitor_product, last 2 snapshots in 24h, avg % change
        cp_ids_result = await self.db.execute(
            select(CompetitorProduct.id)
            .join(Product, CompetitorProduct.product_id == Product.id)
            .where(Product.user_id == self.user_id, CompetitorProduct.is_active.is_(True))
        )
        cp_ids = [r[0] for r in cp_ids_result.all()]

        price_changes: list[float] = []
        if cp_ids:
            for cp_id in cp_ids:
                snapshots_result = await self.db.execute(
                    select(PriceSnapshot.price, PriceSnapshot.old_price, PriceSnapshot.scraped_at)
                    .where(
                        PriceSnapshot.competitor_product_id == cp_id,
                        PriceSnapshot.scraped_at >= day_ago,
                    )
                    .order_by(PriceSnapshot.scraped_at.desc())
                    .limit(2)
                )
                rows = snapshots_result.all()
                if len(rows) >= 2:
                    new_price = float(rows[0].price)
                    prev_price = float(rows[1].price) if rows[1].price else float(rows[1].old_price or rows[1].price)
                    if prev_price and prev_price > 0:
                        pct = (new_price - prev_price) / prev_price * 100
                        price_changes.append(pct)
                elif len(rows) == 1 and rows[0].old_price and float(rows[0].old_price) > 0:
                    pct = (float(rows[0].price) - float(rows[0].old_price)) / float(rows[0].old_price) * 100
                    price_changes.append(pct)

        avg_price_change_24h = (
            sum(price_changes) / len(price_changes) if price_changes else 0.0
        )

        # active_alerts_count: alert_events in last 24h
        active_alerts_result = await self.db.execute(
            select(func.count())
            .select_from(AlertEvent)
            .join(Alert, AlertEvent.alert_id == Alert.id)
            .where(
                Alert.user_id == self.user_id,
                AlertEvent.triggered_at >= day_ago,
            )
        )
        active_alerts_count = active_alerts_result.scalar() or 0

        # critical_alerts_count: from those, where alert.threshold_percent > 15
        critical_result = await self.db.execute(
            select(func.count())
            .select_from(AlertEvent)
            .join(Alert, AlertEvent.alert_id == Alert.id)
            .where(
                Alert.user_id == self.user_id,
                AlertEvent.triggered_at >= day_ago,
                Alert.threshold_percent.isnot(None),
                Alert.threshold_percent > 15,
            )
        )
        critical_alerts_count = critical_result.scalar() or 0

        # revenue_impact_percent: simplified = avg_price_change_24h * total_products (placeholder)
        revenue_impact_percent = avg_price_change_24h * min(total_products, 1) if total_products else 0.0
        revenue_impact_confidence = 0.75

        # products_at_risk: products where any competitor is cheaper by >10%
        products_at_risk_result = await self.db.execute(
            select(Product.id)
            .join(CompetitorProduct, CompetitorProduct.product_id == Product.id)
            .where(
                Product.user_id == self.user_id,
                Product.is_active.is_(True),
                CompetitorProduct.is_active.is_(True),
                CompetitorProduct.last_price.isnot(None),
                CompetitorProduct.last_price < Product.current_price * Decimal("0.9"),
            )
            .distinct()
        )
        products_at_risk = len(products_at_risk_result.all())

        # trend_vs_last_week: compare current with 7 days ago
        # products count 7 days ago (products created before week_ago)
        products_week_ago_result = await self.db.execute(
            select(func.count())
            .select_from(Product)
            .where(
                Product.user_id == self.user_id,
                Product.is_active.is_(True),
                Product.created_at < week_ago,
            )
        )
        products_week_ago = products_week_ago_result.scalar() or 0
        trend_products = (
            ((total_products - products_week_ago) / products_week_ago * 100)
            if products_week_ago
            else 0.0
        )

        # price_change 7 days ago: avg from snapshots in [2 weeks ago, 1 week ago]
        price_changes_week_ago: list[float] = []
        if cp_ids:
            for cp_id in cp_ids:
                snap_result = await self.db.execute(
                    select(PriceSnapshot.price, PriceSnapshot.old_price)
                    .where(
                        PriceSnapshot.competitor_product_id == cp_id,
                        PriceSnapshot.scraped_at >= two_weeks_ago,
                        PriceSnapshot.scraped_at < week_ago,
                    )
                    .order_by(PriceSnapshot.scraped_at.desc())
                    .limit(2)
                )
                rows = snap_result.all()
                if len(rows) >= 2 and rows[1].price and float(rows[1].price) > 0:
                    pct = (float(rows[0].price) - float(rows[1].price)) / float(rows[1].price) * 100
                    price_changes_week_ago.append(pct)
                elif len(rows) == 1 and rows[0].old_price and float(rows[0].old_price) > 0:
                    pct = (float(rows[0].price) - float(rows[0].old_price)) / float(rows[0].old_price) * 100
                    price_changes_week_ago.append(pct)

        avg_price_change_week_ago = (
            sum(price_changes_week_ago) / len(price_changes_week_ago)
            if price_changes_week_ago
            else 0.0
        )
        trend_price_change = avg_price_change_24h - avg_price_change_week_ago

        # alerts 7 days ago
        alerts_week_ago_result = await self.db.execute(
            select(func.count())
            .select_from(AlertEvent)
            .join(Alert, AlertEvent.alert_id == Alert.id)
            .where(
                Alert.user_id == self.user_id,
                AlertEvent.triggered_at >= two_weeks_ago,
                AlertEvent.triggered_at < week_ago,
            )
        )
        alerts_week_ago = alerts_week_ago_result.scalar() or 0
        trend_alerts = (
            ((active_alerts_count - alerts_week_ago) / alerts_week_ago * 100)
            if alerts_week_ago
            else 0.0
        )

        return {
            "total_products": total_products,
            "total_competitors": total_competitors,
            "total_competitor_products": total_competitor_products,
            "avg_price_change_24h": round(avg_price_change_24h, 2),
            "active_alerts_count": active_alerts_count,
            "critical_alerts_count": critical_alerts_count,
            "revenue_impact_percent": round(revenue_impact_percent, 2),
            "revenue_impact_confidence": revenue_impact_confidence,
            "products_at_risk": products_at_risk,
            "trend_vs_last_week": {
                "products": round(trend_products, 2),
                "price_change": round(trend_price_change, 2),
                "alerts": round(trend_alerts, 2),
            },
        }

    async def get_anomalies(self, limit: int = 10) -> list[dict]:
        """
        Anomalies: price changes > 10% in last 24 hours.
        Sorted by abs(change_percent) DESC.

        Returns:
            List of anomaly dicts with id, product_id, product_name, competitor_name,
            marketplace, old_price, new_price, change_percent, direction, severity,
            detected_at, ai_explanation.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)

        result = await self.db.execute(
            select(
                PriceSnapshot.id,
                Product.id.label("product_id"),
                Product.name.label("product_name"),
                Competitor.name.label("competitor_name"),
                Competitor.marketplace,
                PriceSnapshot.old_price,
                PriceSnapshot.price.label("new_price"),
                (
                    (PriceSnapshot.price - PriceSnapshot.old_price)
                    / PriceSnapshot.old_price
                    * 100
                ).label("change_pct"),
                PriceSnapshot.scraped_at.label("detected_at"),
            )
            .select_from(PriceSnapshot)
            .join(CompetitorProduct, PriceSnapshot.competitor_product_id == CompetitorProduct.id)
            .join(Product, CompetitorProduct.product_id == Product.id)
            .join(Competitor, CompetitorProduct.competitor_id == Competitor.id)
            .where(
                Product.user_id == self.user_id,
                PriceSnapshot.scraped_at >= cutoff,
                PriceSnapshot.old_price.isnot(None),
                PriceSnapshot.old_price > 0,
                func.abs(
                    (PriceSnapshot.price - PriceSnapshot.old_price)
                    / PriceSnapshot.old_price
                    * 100
                )
                > 10,
            )
            .order_by(
                func.abs(
                    (PriceSnapshot.price - PriceSnapshot.old_price)
                    / PriceSnapshot.old_price
                    * 100
                ).desc()
            )
            .limit(limit)
        )

        items: list[dict] = []
        for r in result.all():
            change_pct = float(r.change_pct)
            direction = "up" if change_pct > 0 else "down"
            abs_pct = abs(change_pct)
            if abs_pct > 25:
                severity = "critical"
            elif abs_pct >= 15:
                severity = "warning"
            else:
                severity = "info"

            items.append({
                "id": r.id,
                "product_id": str(r.product_id),
                "product_name": r.product_name,
                "competitor_name": r.competitor_name,
                "marketplace": r.marketplace,
                "old_price": float(r.old_price),
                "new_price": float(r.new_price),
                "change_percent": round(change_pct, 2),
                "direction": direction,
                "severity": severity,
                "detected_at": r.detected_at,
                "ai_explanation": None,
            })

        return items

    async def get_aggregate_trend(
        self, period_days: int = 30, forecast_days: int = 7
    ) -> dict:
        """
        Aggregate trend for chart: my products avg vs competitors avg by day.
        Forecast: linear extrapolation from last 14 points.

        Returns:
            dict with labels, my_products_avg, competitors_avg, forecast, forecast_labels.
        """
        now = datetime.now(timezone.utc)
        period_start = now - timedelta(days=period_days)

        labels: list[str] = []
        my_products_avg: list[float] = []
        competitors_avg: list[float] = []

        for i in range(period_days):
            day_start = (period_start + timedelta(days=i)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            day_end = day_start + timedelta(days=1)
            labels.append(day_start.strftime("%Y-%m-%d"))

            # my_products_avg: avg current_price of user's active products
            # (no history - use current value for all days)
            my_result = await self.db.execute(
                select(func.avg(Product.current_price))
                .where(
                    Product.user_id == self.user_id,
                    Product.is_active.is_(True),
                    Product.created_at < day_end,
                )
            )
            my_avg = my_result.scalar() or 0
            my_products_avg.append(float(my_avg))

            # competitors_avg: avg price from price_snapshots for user's competitor_products
            comp_result = await self.db.execute(
                select(func.avg(PriceSnapshot.price))
                .select_from(PriceSnapshot)
                .join(CompetitorProduct, PriceSnapshot.competitor_product_id == CompetitorProduct.id)
                .join(Product, CompetitorProduct.product_id == Product.id)
                .where(
                    Product.user_id == self.user_id,
                    PriceSnapshot.scraped_at >= day_start,
                    PriceSnapshot.scraped_at < day_end,
                )
            )
            comp_avg = comp_result.scalar() or 0
            competitors_avg.append(float(comp_avg))

        # Linear regression on last 14 points of competitors_avg for forecast
        forecast: list[float] = []
        forecast_labels: list[str] = []
        last_14 = [c for c in competitors_avg[-14:] if c > 0]
        if len(last_14) >= 2:
            n = len(last_14)
            x = list(range(n))
            y = last_14
            sum_x = sum(x)
            sum_y = sum(y)
            sum_xy = sum(xi * yi for xi, yi in zip(x, y))
            sum_x2 = sum(xi * xi for xi in x)
            denom = n * sum_x2 - sum_x * sum_x
            slope = (n * sum_xy - sum_x * sum_y) / denom if denom else 0
            intercept = (sum_y - slope * sum_x) / n if n else 0

            for i in range(1, forecast_days + 1):
                pred = slope * (n + i - 1) + intercept
                forecast.append(round(max(0, pred), 2))
                fd = now + timedelta(days=i)
                forecast_labels.append(fd.strftime("%Y-%m-%d"))
        else:
            last_val = competitors_avg[-1] if competitors_avg else 0
            for i in range(1, forecast_days + 1):
                forecast.append(round(last_val, 2))
                fd = now + timedelta(days=i)
                forecast_labels.append(fd.strftime("%Y-%m-%d"))

        return {
            "labels": labels,
            "my_products_avg": [round(v, 2) for v in my_products_avg],
            "competitors_avg": [round(v, 2) for v in competitors_avg],
            "forecast": forecast,
            "forecast_labels": forecast_labels,
        }

    async def get_dashboard_summary(self) -> dict:
        """
        Dashboard summary for frontend: total_products, total_competitors,
        total_tracked_items, last_scrape_at, alerts_triggered_today,
        price_changes_today, top_changes, active_promos.
        """
        now = datetime.now(timezone.utc)
        day_ago = now - timedelta(hours=24)

        kpi = await self.get_kpi()
        total_products = kpi["total_products"]
        total_competitors = kpi["total_competitors"]
        total_tracked_items = kpi["total_competitor_products"]
        alerts_triggered_today = kpi["active_alerts_count"]

        # last_scrape_at: max from scrape_logs for user's competitor_products
        last_scrape_result = await self.db.execute(
            select(func.max(ScrapeLog.created_at))
            .select_from(ScrapeLog)
            .join(CompetitorProduct, ScrapeLog.competitor_product_id == CompetitorProduct.id)
            .join(Product, CompetitorProduct.product_id == Product.id)
            .where(Product.user_id == self.user_id)
        )
        last_scrape_at = last_scrape_result.scalar_one_or_none()

        # price_changes_today and top_changes: from price_snapshots in last 24h
        changes_result = await self.db.execute(
            select(
                Product.name.label("product_name"),
                Competitor.name.label("competitor_name"),
                PriceSnapshot.old_price,
                PriceSnapshot.price.label("new_price"),
                (
                    (PriceSnapshot.price - PriceSnapshot.old_price)
                    / PriceSnapshot.old_price
                    * 100
                ).label("change_pct"),
            )
            .select_from(PriceSnapshot)
            .join(CompetitorProduct, PriceSnapshot.competitor_product_id == CompetitorProduct.id)
            .join(Product, CompetitorProduct.product_id == Product.id)
            .join(Competitor, CompetitorProduct.competitor_id == Competitor.id)
            .where(
                Product.user_id == self.user_id,
                PriceSnapshot.scraped_at >= day_ago,
                PriceSnapshot.old_price.isnot(None),
                PriceSnapshot.old_price > 0,
            )
        )
        rows = changes_result.all()
        drops = sum(1 for r in rows if float(r.change_pct) < 0)
        increases = sum(1 for r in rows if float(r.change_pct) > 0)
        sorted_rows = sorted(rows, key=lambda r: abs(float(r.change_pct)), reverse=True)
        top_changes = [
            {
                "product_name": r.product_name,
                "competitor_name": r.competitor_name,
                "old_price": float(r.old_price),
                "new_price": float(r.new_price),
                "change_percent": round(float(r.change_pct), 2),
            }
            for r in sorted_rows[:5]
        ]

        # active_promos: competitor_products with non-null promo_label
        promos_result = await self.db.execute(
            select(Competitor.name, Product.name, CompetitorProduct.last_promo_label)
            .select_from(CompetitorProduct)
            .join(Product, CompetitorProduct.product_id == Product.id)
            .join(Competitor, CompetitorProduct.competitor_id == Competitor.id)
            .where(
                Product.user_id == self.user_id,
                CompetitorProduct.is_active.is_(True),
                CompetitorProduct.last_promo_label.isnot(None),
                CompetitorProduct.last_promo_label != "",
            )
        )
        active_promos = [
            {"competitor_name": c, "product_name": p, "promo_label": pl or ""}
            for c, p, pl in promos_result.all()
        ]

        return {
            "total_products": total_products,
            "total_competitors": total_competitors,
            "total_tracked_items": total_tracked_items,
            "last_scrape_at": last_scrape_at.isoformat() if last_scrape_at else None,
            "alerts_triggered_today": alerts_triggered_today,
            "price_changes_today": {"drops": drops, "increases": increases},
            "top_changes": top_changes,
            "active_promos": active_promos,
        }
