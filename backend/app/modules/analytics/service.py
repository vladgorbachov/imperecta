"""Forecast and benchmark analytics (FactPrice + FactListing + UserProduct)."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.core import UserProduct
from app.models.dimensions import DimMarketplace, DimProduct
from app.models.facts import FactListing, FactPrice


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
    """Price history and simple forecast from FactPrice (per listing)."""

    def __init__(self, db: AsyncSession, user_id: UUID):
        self.db = db
        self.user_id = user_id

    async def _user_owns_product(self, product_id: UUID) -> bool:
        row = await self.db.scalar(
            select(UserProduct.id).where(
                UserProduct.user_id == self.user_id,
                UserProduct.product_id == product_id,
                UserProduct.is_active.is_(True),
            ),
        )
        return row is not None

    async def product_forecast(self, product_id: UUID, forecast_days: int = 14) -> dict:
        """Forecast from aggregated FactPrice rows across listings for this product."""
        if not await self._user_owns_product(product_id):
            return {
                "product_id": str(product_id),
                "product_name": "",
                "current_price": 0.0,
                "history": [],
                "forecast": [],
                "confidence": 0.0,
                "trend": "stable",
                "recommendation": "Track this product first.",
            }

        pname = await self.db.scalar(select(DimProduct.name).where(DimProduct.id == product_id))
        stmt = (
            select(FactPrice.date_id, FactPrice.price, FactPrice.price_eur)
            .join(FactListing, FactPrice.listing_id == FactListing.id)
            .where(
                FactListing.product_id == product_id,
                FactListing.is_active.is_(True),
            )
            .order_by(FactPrice.date_id)
            .limit(120)
        )
        result = await self.db.execute(stmt)
        rows = result.all()
        if len(rows) < 2:
            last = float(rows[0][1]) if rows else 0.0
            return {
                "product_id": str(product_id),
                "product_name": pname or "",
                "current_price": last,
                "history": [],
                "forecast": [],
                "confidence": 0.0,
                "trend": "stable",
                "recommendation": "Collect more price history.",
            }

        # One point per date_id: average price across listings
        by_date: dict[int, list[float]] = {}
        for date_id, price, price_eur in rows:
            if date_id not in by_date:
                by_date[date_id] = []
            val = float(price_eur) if price_eur is not None else float(price)
            by_date[date_id].append(val)
        sorted_ids = sorted(by_date.keys())
        series = [sum(by_date[i]) / len(by_date[i]) for i in sorted_ids]

        x = [float(i) for i in range(len(series))]
        slope, intercept, r2 = linear_regression(x, series)
        trend = "up" if slope > 0 else "down" if slope < 0 else "stable"

        history = [{"date_id": sorted_ids[i], "price": round(series[i], 4)} for i in range(len(series))]
        forecast = []
        last_x = float(len(series) - 1)
        for k in range(1, forecast_days + 1):
            px = last_x + float(k)
            forecast.append({"day": k, "price": round(slope * px + intercept, 4)})

        return {
            "product_id": str(product_id),
            "product_name": pname or "",
            "current_price": round(series[-1], 4),
            "history": history[-30:],
            "forecast": forecast[:forecast_days],
            "confidence": round(r2, 1),
            "trend": trend,
            "recommendation": "Monitor competitor listings for the same SKU.",
        }

    async def market_forecast(self, forecast_days: int = 7) -> dict:
        """Aggregate outlook across tracked products."""

        _ = forecast_days
        pids = (
            await self.db.execute(
                select(UserProduct.product_id).where(
                    UserProduct.user_id == self.user_id,
                    UserProduct.is_active.is_(True),
                ),
            )
        ).scalars().all()
        products_forecast: list[dict] = []
        for pid in pids[:20]:
            f = await self.product_forecast(pid, forecast_days=forecast_days)
            products_forecast.append(
                {
                    "product_id": f["product_id"],
                    "trend": f["trend"],
                    "current_price": f["current_price"],
                },
            )
        return {
            "summary": "Portfolio trend snapshot from fact_price.",
            "confidence": 0.0,
            "products_forecast": products_forecast,
            "risk_factors": [],
        }

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
            "confidence": 0.0,
            "reasoning": "Elasticity model (no FactPrice dependency).",
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
    """Compare listings (same dim_product) across marketplaces using FactPrice + FactListing."""

    def __init__(self, db: AsyncSession, user_id: UUID):
        self.db = db
        self.user_id = user_id

    async def get_competitor_scores(self) -> list[dict]:
        """Score = relative price vs cheapest competitor listing (same product)."""
        tracked = (
            await self.db.execute(
                select(UserProduct.product_id, DimProduct.name)
                .join(DimProduct, UserProduct.product_id == DimProduct.id)
                .where(
                    UserProduct.user_id == self.user_id,
                    UserProduct.is_active.is_(True),
                ),
            )
        ).all()
        out: list[dict] = []
        for product_id, name in tracked:
            stmt = (
                select(
                    FactListing.id,
                    FactListing.last_price_eur,
                    FactListing.last_price,
                    DimMarketplace.name,
                )
                .join(DimMarketplace, FactListing.marketplace_id == DimMarketplace.id)
                .where(
                    FactListing.product_id == product_id,
                    FactListing.is_active.is_(True),
                )
            )
            rows = (await self.db.execute(stmt)).all()
            prices: list[float] = []
            for _lid, lp_eur, lp, _mn in rows:
                if lp_eur is not None:
                    prices.append(float(lp_eur))
                elif lp is not None:
                    prices.append(float(lp))
            if len(prices) < 2:
                continue
            lo = min(prices)
            hi = max(prices)
            spread = ((hi - lo) / lo * 100.0) if lo > 0 else 0.0
            out.append(
                {
                    "product_id": str(product_id),
                    "product_name": name,
                    "price_spread_pct": round(spread, 2),
                    "listing_count": len(prices),
                },
            )
        return out

    async def get_comparison_matrix(self) -> dict:
        """Matrix of user tracked products vs marketplace listing prices."""
        tracked = (
            await self.db.execute(
                select(UserProduct.product_id, DimProduct.name)
                .join(DimProduct, UserProduct.product_id == DimProduct.id)
                .where(
                    UserProduct.user_id == self.user_id,
                    UserProduct.is_active.is_(True),
                ),
            )
        ).all()
        if not tracked:
            return {"products": [], "competitors": [], "matrix": [], "message": None}

        tracked_ids = [t[0] for t in tracked]
        products = [{"id": str(pid), "title": title} for pid, title in tracked]

        stmt = (
            select(
                FactListing.product_id,
                DimMarketplace.marketplace_code,
                FactListing.last_price_eur,
                FactListing.last_price,
            )
            .join(DimMarketplace, FactListing.marketplace_id == DimMarketplace.id)
            .where(
                FactListing.product_id.in_(tracked_ids),
                FactListing.is_active.is_(True),
            )
        )
        raw = (await self.db.execute(stmt)).all()
        row_map: dict[tuple[UUID, str], float | None] = {}
        mset: set[str] = set()
        for pid, mcode, peur, p in raw:
            mset.add(mcode)
            val = float(peur) if peur is not None else (float(p) if p is not None else None)
            row_map[(pid, mcode)] = val

        competitors = sorted(mset)
        matrix: list[list[float | None]] = []
        for pid, _title in tracked:
            matrix.append([row_map.get((pid, mcode)) for mcode in competitors])

        return {
            "products": products,
            "competitors": competitors,
            "matrix": matrix,
            "message": None,
        }
