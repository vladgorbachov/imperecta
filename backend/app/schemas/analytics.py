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


class TopChange(BaseModel):
    """Top price change item."""

    product_name: str
    competitor_name: str
    old_price: Decimal
    new_price: Decimal
    change_percent: float


class ActivePromo(BaseModel):
    """Active promo item."""

    competitor_name: str
    product_name: str
    promo_label: str


class DashboardSummaryResponse(BaseModel):
    """Dashboard summary response."""

    total_products: int
    total_competitors: int
    total_tracked_items: int
    last_scrape_at: datetime | None
    alerts_triggered_today: int
    price_changes_today: dict
    top_changes: list[TopChange]
    active_promos: list[ActivePromo]


class AnomalyItem(BaseModel):
    """Anomaly item (change > 15%)."""

    product_name: str
    competitor_name: str
    old_price: Decimal
    new_price: Decimal
    change_percent: float
    detected_at: datetime


class AnomaliesResponse(BaseModel):
    """Anomalies response."""

    items: list[AnomalyItem]
