"""Analytics response schemas."""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


class PriceHistoryDataPoint(BaseModel):
    """Single price data point."""

    date: date | datetime
    price: Decimal
    promo_label: str | None
    in_stock: bool


class PriceHistoryCompetitor(BaseModel):
    """Competitor price history."""

    competitor_name: str
    competitor_product_id: UUID
    data_points: list[PriceHistoryDataPoint]


class PriceHistoryResponse(BaseModel):
    """Price history response."""

    product_name: str
    my_price: Decimal
    competitors: list[PriceHistoryCompetitor]


class ComparisonCompetitor(BaseModel):
    """Competitor comparison item."""

    name: str
    price: Decimal | None
    diff_amount: Decimal | None
    diff_percent: float | None
    promo_label: str | None
    in_stock: bool | None
    trend: str  # up, down, stable


class ComparisonResponse(BaseModel):
    """Price comparison response."""

    my_price: Decimal
    competitors: list[ComparisonCompetitor]


class SimulateRequest(BaseModel):
    """Request body for POST /api/analytics/simulate."""

    product_id: UUID | None = None
    price_change_pct: float  # -30 to +30
    volume_change_pct: float = 0  # -50 to +50


class AdvancedSimulationRequest(BaseModel):
    """Request body for POST /api/analytics/advanced-simulation."""

    price_change_pct: float
    volume_change_pct: float = 0
    ad_budget_change_pct: float = 0
    inflation_pct: float = 0
    season: str = "normal"  # "normal", "holiday", "sale"
