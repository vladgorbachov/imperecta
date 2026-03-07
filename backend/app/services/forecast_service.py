"""Price forecasting and scenario simulation using statistical methods."""

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CompetitorProduct, PriceSnapshot, Product


def linear_regression(x: list[float], y: list[float]) -> tuple[float, float, float]:
    """
    Simple linear regression. Returns (slope, intercept, r_squared).
    No numpy dependency.
    """
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

    # R-squared
    ss_res = sum((yi - (slope * xi + intercept)) ** 2 for xi, yi in zip(x, y))
    ss_tot = sum((yi - sum_y / n) ** 2 for yi in y)
    r_squared = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0.0

    return slope, intercept, max(0.0, min(1.0, r_squared))


class ForecastService:
    """Price forecasting and scenario simulation using statistical methods."""

    def __init__(self, db: AsyncSession, user_id: UUID):
        self.db = db
        self.user_id = user_id

    async def product_forecast(
        self, product_id: UUID, forecast_days: int = 14
    ) -> dict:
        """
        Forecast price trend for a specific product based on competitor price history.
        Uses linear regression for trend extrapolation.

        Returns:
            dict with product_id, product_name, current_price, history, forecast,
            confidence, trend, recommendation.
        """
        # Get product and verify ownership
        product_result = await self.db.execute(
            select(Product).where(
                Product.id == product_id,
                Product.user_id == self.user_id,
            )
        )
        product = product_result.scalar_one_or_none()
        if not product:
            raise ValueError("Product not found")

        my_price = float(product.current_price)
        cutoff = datetime.now(timezone.utc) - timedelta(days=90)

        # Get competitor_product ids for this product
        cp_result = await self.db.execute(
            select(CompetitorProduct.id).where(
                CompetitorProduct.product_id == product_id,
                CompetitorProduct.is_active.is_(True),
            )
        )
        cp_ids = [r[0] for r in cp_result.all()]

        history: list[dict] = []
        daily_avg_map: dict[str, float] = {}

        if cp_ids:
            # Aggregate price_snapshots by date (avg price per day)
            date_col = func.date_trunc("day", PriceSnapshot.scraped_at)
            agg_result = await self.db.execute(
                select(
                    date_col.label("dt"),
                    func.avg(PriceSnapshot.price).label("avg_price"),
                )
                .where(
                    PriceSnapshot.competitor_product_id.in_(cp_ids),
                    PriceSnapshot.scraped_at >= cutoff,
                )
                .group_by(date_col)
                .order_by(date_col)
            )
            for r in agg_result.all():
                dt_val = r.dt
                dt_str = dt_val.strftime("%Y-%m-%d") if hasattr(dt_val, "strftime") else str(dt_val)[:10]
                avg_p = float(r.avg_price)
                daily_avg_map[dt_str] = avg_p
                history.append({
                    "date": dt_str,
                    "avg_competitor_price": round(avg_p, 2),
                    "my_price": round(my_price, 2),
                })

        # Linear regression on historical data
        if len(history) >= 2:
            x = list(range(len(history)))
            y = [h["avg_competitor_price"] for h in history]
            slope, intercept, r_squared = linear_regression(x, y)

            # Std dev of residuals for confidence interval
            residuals = [yi - (slope * xi + intercept) for xi, yi in zip(x, y)]
            std_dev = (sum(r**2 for r in residuals) / len(residuals)) ** 0.5 if residuals else 0
            interval_width = 1.5 * std_dev

            # Forecast
            last_x = len(history) - 1
            forecast: list[dict] = []
            for i in range(1, forecast_days + 1):
                pred_x = last_x + i
                pred_price = slope * pred_x + intercept
                lower = max(0, pred_price - interval_width)
                upper = pred_price + interval_width
                pred_date = (datetime.now(timezone.utc) + timedelta(days=i)).strftime("%Y-%m-%d")
                forecast.append({
                    "date": pred_date,
                    "predicted_price": round(max(0, pred_price), 2),
                    "lower_bound": round(lower, 2),
                    "upper_bound": round(upper, 2),
                })

            # Trend: slope as % of average price
            avg_price = sum(y) / len(y)
            slope_pct = (slope / avg_price * 100) if avg_price else 0
            if slope_pct > 1:
                trend = "rising"
            elif slope_pct < -1:
                trend = "declining"
            else:
                trend = "stable"

            # Recommendation
            diff_pct = (my_price - avg_price) / avg_price * 100 if avg_price else 0
            if trend == "declining" and diff_pct > 5:
                recommendation = f"Consider reducing price by 3-5% within 7 days. Competitors avg {avg_price:.0f}, you are {diff_pct:.1f}% above."
            elif trend == "rising" and diff_pct < -5:
                recommendation = f"Market is rising. Consider increasing price by 2-4% to capture margin."
            elif trend == "stable":
                recommendation = "Market is stable. Monitor competitor promotions before adjusting."
            else:
                recommendation = "Continue monitoring. No immediate action recommended."

            confidence = r_squared
        else:
            forecast = []
            trend = "stable"
            confidence = 0.0
            recommendation = "Insufficient historical data for forecast. Add more competitor products and wait for price snapshots."

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
        """
        Aggregate market forecast across all user's products.

        Returns:
            dict with summary, confidence, products_forecast, risk_factors.
        """
        products_result = await self.db.execute(
            select(Product.id, Product.name).where(
                Product.user_id == self.user_id,
                Product.is_active.is_(True),
            )
        )
        products = products_result.all()

        products_forecast: list[dict] = []
        total_slope_sum = 0.0
        count_with_data = 0
        risk_factors: list[str] = []

        for product_id, product_name in products:
            try:
                pf = await self.product_forecast(product_id, forecast_days=forecast_days)
                if pf["history"]:
                    # Estimate expected change from forecast
                    if pf["forecast"]:
                        last_hist = pf["history"][-1]["avg_competitor_price"]
                        first_fc = pf["forecast"][0]["predicted_price"]
                        expected_change = (first_fc - last_hist) / last_hist * 100 if last_hist else 0
                    else:
                        expected_change = 0.0
                    products_forecast.append({
                        "product_id": str(product_id),
                        "name": product_name,
                        "trend": pf["trend"],
                        "expected_change_pct": round(expected_change, 2),
                    })
                    if pf["trend"] == "declining":
                        total_slope_sum -= 1
                        count_with_data += 1
                    elif pf["trend"] == "rising":
                        total_slope_sum += 1
                        count_with_data += 1
            except ValueError:
                pass

        # Summary
        if count_with_data > 0:
            avg_trend = total_slope_sum / count_with_data
            if avg_trend < -0.3:
                summary = f"Market is expected to decline ~2-3% over next {forecast_days} days."
                risk_factors.append("Seasonal decline expected")
            elif avg_trend > 0.3:
                summary = f"Market is expected to rise ~2-3% over next {forecast_days} days."
            else:
                summary = f"Market is expected to remain stable over next {forecast_days} days."
        else:
            summary = "Insufficient data for market forecast. Add products and competitor tracking."

        # Check for promotions (from price_snapshots with promo)
        promo_result = await self.db.execute(
            select(func.count())
            .select_from(PriceSnapshot)
            .join(CompetitorProduct, PriceSnapshot.competitor_product_id == CompetitorProduct.id)
            .join(Product, CompetitorProduct.product_id == Product.id)
            .where(
                Product.user_id == self.user_id,
                PriceSnapshot.scraped_at >= datetime.now(timezone.utc) - timedelta(days=7),
                PriceSnapshot.promo_label.isnot(None),
                PriceSnapshot.promo_label != "",
            )
        )
        promo_count = promo_result.scalar() or 0
        if promo_count > 3:
            risk_factors.append(f"{promo_count} competitors running promotions in last 7 days")

        confidence = min(0.85, 0.5 + count_with_data * 0.05) if products else 0.0

        return {
            "summary": summary,
            "confidence": round(confidence, 2),
            "products_forecast": products_forecast,
            "risk_factors": risk_factors,
        }

    async def simulate_scenario(
        self,
        product_id: UUID | None,
        price_change_pct: float,
        volume_change_pct: float = 0,
    ) -> dict:
        """
        Simulate what happens if user changes price.
        Uses price elasticity estimation (default -1.5 for e-commerce when data is sparse).
        """
        # Clamp inputs
        price_change_pct = max(-30, min(30, price_change_pct))
        volume_change_pct = max(-50, min(50, volume_change_pct))

        # Default elasticity for e-commerce (no volume history available)
        DEFAULT_ELASTICITY = -1.5
        elasticity = DEFAULT_ELASTICITY

        # If user provided volume_change, we could back-calculate elasticity from historical
        # For now use default
        predicted_sales_change_pct = price_change_pct * elasticity

        # Revenue change: (1 + P%) * (1 + Q%) - 1
        revenue_factor = (1 + price_change_pct / 100) * (1 + predicted_sales_change_pct / 100)
        predicted_revenue_change_pct = (revenue_factor - 1) * 100

        # Margin: assume 25% base. Cost = 75% of price. New margin when price changes.
        BASE_MARGIN = 0.25
        cost_ratio = 1 - BASE_MARGIN
        if price_change_pct != -100:
            new_margin_estimate = 1 - cost_ratio / (1 + price_change_pct / 100)
        else:
            new_margin_estimate = 0.01
        new_margin_estimate = max(0.01, min(0.99, new_margin_estimate))
        predicted_margin_change_pct = (
            (new_margin_estimate - BASE_MARGIN) / BASE_MARGIN * 100
            if BASE_MARGIN
            else 0
        )

        # Confidence: low when using default elasticity
        confidence = 0.6

        reasoning = (
            f"Based on default price elasticity of {DEFAULT_ELASTICITY} for e-commerce "
            "(typical for online retail). No historical volume data available for calibration."
        )

        return {
            "input": {
                "price_change_pct": round(price_change_pct, 1),
                "volume_change_pct": round(volume_change_pct, 1),
            },
            "predicted_sales_change_pct": round(predicted_sales_change_pct, 1),
            "predicted_revenue_change_pct": round(predicted_revenue_change_pct, 1),
            "predicted_margin_change_pct": round(predicted_margin_change_pct, 1),
            "current_margin_estimate": round(BASE_MARGIN * 100, 1),
            "new_margin_estimate": round(new_margin_estimate * 100, 1),
            "confidence": confidence,
            "reasoning": reasoning,
        }

    async def advanced_simulation(
        self,
        price_change_pct: float,
        volume_change_pct: float,
        ad_budget_change_pct: float,
        inflation_pct: float,
        season: str,
    ) -> dict:
        """Extended simulation with season, ad budget, and inflation factors."""
        base = await self.simulate_scenario(None, price_change_pct, volume_change_pct)

        season_multiplier = {"normal": 1.0, "holiday": 1.3, "sale": 1.5}.get(season, 1.0)
        ad_effect = ad_budget_change_pct * 0.3
        inflation_effect = -inflation_pct * 0.5

        adjusted_sales = (
            base["predicted_sales_change_pct"] * season_multiplier
            + ad_effect
            + inflation_effect
        )

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
