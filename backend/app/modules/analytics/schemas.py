"""Analytics response schemas."""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


class PriceHistoryDataPoint(BaseModel):
    date: date | datetime
    price: Decimal
    promo_label: str | None
    in_stock: bool


class PriceHistoryCompetitor(BaseModel):
    competitor_name: str
    competitor_product_id: UUID
    data_points: list[PriceHistoryDataPoint]


class PriceHistoryResponse(BaseModel):
    product_name: str
    my_price: Decimal
    competitors: list[PriceHistoryCompetitor]


class ComparisonCompetitor(BaseModel):
    name: str
    price: Decimal | None
    diff_amount: Decimal | None
    diff_percent: float | None
    promo_label: str | None
    in_stock: bool | None
    trend: str


class ComparisonResponse(BaseModel):
    my_price: Decimal
    competitors: list[ComparisonCompetitor]


class SimulateRequest(BaseModel):
    product_id: UUID | None = None
    price_change_pct: float
    volume_change_pct: float = 0


class AdvancedSimulationRequest(BaseModel):
    price_change_pct: float
    volume_change_pct: float = 0
    ad_budget_change_pct: float = 0
    inflation_pct: float = 0
    season: str = "normal"
