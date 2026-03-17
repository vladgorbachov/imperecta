"""Forecast and benchmark analytics services."""

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Competitor, CompetitorProduct, PriceSnapshot, Product


def linear_regression(x: list[float], y: list[float]) -> tuple[float, float, float]:
    """Simple linear regression. Returns (slope, intercept, r_squared)."""
    n = len(x)
    if n < 2:
        return 0.0, float(y[0]) if y else 0.0, 0.0
    sum_x = sum(x)
    sum_y = sum(y)
    sum_xy = sum(xi * yi for xi, yi in zip(x, y))
    sum_x2 = sum(xi**2 for xi in x)
    denom = n * sum_x2 - sum_x**2
    if denom == 0:
        return 0.0, sum_y / n, 0.0
    slope = (n * sum_xy - sum_x * sum_y) / denom
    intercept = (sum_y - slope * sum_x) / n
    ss_res = sum((yi - (slope * xi + intercept)) ** 2 for xi, yi in zip(x, y))
    ss_tot = sum((yi - sum_y / n) ** 2 for yi in y)
    r_squared = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0.0
    return slope, intercept, max(0.0, min(1.0, r_squared))


class ForecastService:
    """Price forecasting and scenario simulation service."""

    def __init__(self, db: AsyncSession, user_id: UUID):
        self.db = db
        self.user_id = user_id

    async def product_forecast(self, product_id: UUID, forecast_days: int = 14) -> dict:
        product_result = await self.db.execute(
            select(Product).where(Product.id == product_id, Product.user_id == self.user_id)
        )
        product = product_result.scalar_one_or_none()
        if not product:
            raise ValueError("Product not found")
        my_price = float(product.current_price)
        cutoff = datetime.now(timezone.utc) - timedelta(days=90)
        cp_result = await self.db.execute(
            select(CompetitorProduct.id).where(CompetitorProduct.product_id == product_id, CompetitorProduct.is_active.is_(True))
        )
        cp_ids = [r[0] for r in cp_result.all()]
        history: list[dict] = []
        if cp_ids:
            date_col = func.date_trunc("day", PriceSnapshot.scraped_at)
            agg_result = await self.db.execute(
                select(date_col.label("dt"), func.avg(PriceSnapshot.price).label("avg_price"))
                .where(PriceSnapshot.competitor_product_id.in_(cp_ids), PriceSnapshot.scraped_at >= cutoff)
                .group_by(date_col)
                .order_by(date_col)
            )
            for row in agg_result.all():
                dt_str = row.dt.strftime("%Y-%m-%d") if hasattr(row.dt, "strftime") else str(row.dt)[:10]
                history.append({"date": dt_str, "avg_competitor_price": round(float(row.avg_price), 2), "my_price": round(my_price, 2)})

        if len(history) >= 2:
            x = list(range(len(history)))
            y = [h["avg_competitor_price"] for h in history]
            slope, intercept, r_squared = linear_regression(x, y)
            residuals = [yi - (slope * xi + intercept) for xi, yi in zip(x, y)]
            std_dev = (sum(r**2 for r in residuals) / len(residuals)) ** 0.5 if residuals else 0
            interval_width = 1.5 * std_dev
            last_x = len(history) - 1
            forecast: list[dict] = []
            for i in range(1, forecast_days + 1):
                pred_x = last_x + i
                pred_price = slope * pred_x + intercept
                pred_date = (datetime.now(timezone.utc) + timedelta(days=i)).strftime("%Y-%m-%d")
                forecast.append(
                    {
                        "date": pred_date,
                        "predicted_price": round(max(0, pred_price), 2),
                        "lower_bound": round(max(0, pred_price - interval_width), 2),
                        "upper_bound": round(pred_price + interval_width, 2),
                    }
                )
            avg_price = sum(y) / len(y)
            slope_pct = (slope / avg_price * 100) if avg_price else 0
            trend = "rising" if slope_pct > 1 else ("declining" if slope_pct < -1 else "stable")
            recommendation = "Continue monitoring."
            confidence = r_squared
        else:
            forecast = []
            trend = "stable"
            confidence = 0.0
            recommendation = "Insufficient historical data for forecast."

        return {
            "product_id": str(product_id),
            "product_name": product.name,
            "current_price": round(my_price, 2),
            "history": history,
            "forecast": forecast,
            "confidence": round(confidence, 2),
            "trend": trend,
            "recommendation": recommendation,
        }

    async def market_forecast(self, forecast_days: int = 7) -> dict:
        products_result = await self.db.execute(select(Product.id, Product.name).where(Product.user_id == self.user_id, Product.is_active.is_(True)))
        products = products_result.all()
        products_forecast: list[dict] = []
        for product_id, product_name in products:
            pf = await self.product_forecast(product_id, forecast_days=forecast_days)
            if pf["history"]:
                products_forecast.append({"product_id": str(product_id), "name": product_name, "trend": pf["trend"], "expected_change_pct": 0})
        return {"summary": "Forecast generated", "confidence": 0.6, "products_forecast": products_forecast, "risk_factors": []}

    async def simulate_scenario(self, product_id: UUID | None, price_change_pct: float, volume_change_pct: float = 0) -> dict:
        _ = product_id
        price_change_pct = max(-30, min(30, price_change_pct))
        volume_change_pct = max(-50, min(50, volume_change_pct))
        elasticity = -1.5
        predicted_sales_change_pct = price_change_pct * elasticity
        revenue_factor = (1 + price_change_pct / 100) * (1 + predicted_sales_change_pct / 100)
        predicted_revenue_change_pct = (revenue_factor - 1) * 100
        return {
            "input": {"price_change_pct": round(price_change_pct, 1), "volume_change_pct": round(volume_change_pct, 1)},
            "predicted_sales_change_pct": round(predicted_sales_change_pct, 1),
            "predicted_revenue_change_pct": round(predicted_revenue_change_pct, 1),
            "predicted_margin_change_pct": 0.0,
            "current_margin_estimate": 25.0,
            "new_margin_estimate": 25.0,
            "confidence": 0.6,
            "reasoning": "Default elasticity model",
        }

    async def advanced_simulation(
        self,
        price_change_pct: float,
        volume_change_pct: float,
        ad_budget_change_pct: float,
        inflation_pct: float,
        season: str,
    ) -> dict:
        base = await self.simulate_scenario(None, price_change_pct, volume_change_pct)
        season_multiplier = {"normal": 1.0, "holiday": 1.3, "sale": 1.5}.get(season, 1.0)
        ad_effect = ad_budget_change_pct * 0.3
        inflation_effect = -inflation_pct * 0.5
        adjusted_sales = base["predicted_sales_change_pct"] * season_multiplier + ad_effect + inflation_effect
        return {
            **base,
            "predicted_sales_change_pct": round(adjusted_sales, 1),
            "factors_applied": {
                "season": season,
                "season_multiplier": season_multiplier,
                "ad_effect": round(ad_effect, 1),
                "inflation_effect": round(inflation_effect, 1),
            },
        }


class BenchmarkService:
    """Competitor benchmark scoring and comparison matrix."""

    def __init__(self, db: AsyncSession, user_id: UUID):
        self.db = db
        self.user_id = user_id

    async def get_competitor_scores(self) -> list[dict]:
        competitors_result = await self.db.execute(select(Competitor.id, Competitor.name, Competitor.marketplace).where(Competitor.user_id == self.user_id))
        competitors = competitors_result.all()
        return [
            {
                "competitor_id": str(comp_id),
                "competitor_name": comp_name,
                "marketplace": marketplace,
                "score": 0,
                "aggressiveness": "passive",
                "components": {
                    "price_aggressiveness": 0,
                    "activity_level": 0,
                    "promotion_intensity": 0,
                    "market_coverage": 0,
                },
                "price_index": 100.0,
                "last_change_pct": 0.0,
                "trend_30d": [0.0] * 30,
            }
            for comp_id, comp_name, marketplace in competitors
        ]

    async def get_comparison_matrix(self) -> dict:
        products_result = await self.db.execute(select(Product.id, Product.name).where(Product.user_id == self.user_id, Product.is_active.is_(True)).order_by(Product.name))
        competitors_result = await self.db.execute(select(Competitor.id, Competitor.name, Competitor.marketplace).where(Competitor.user_id == self.user_id).order_by(Competitor.name))
        products = products_result.all()
        competitors = competitors_result.all()
        matrix = [[None for _ in competitors] for _ in products]
        return {
            "products": [{"id": str(p.id), "name": p.name} for p in products],
            "competitors": [{"id": str(c.id), "name": c.name, "marketplace": c.marketplace} for c in competitors],
            "matrix": matrix,
        }
