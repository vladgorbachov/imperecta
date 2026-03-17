from datetime import datetime

from pydantic import BaseModel


class GlobalProductResponse(BaseModel):
    id: int
    marketplace_id: int
    marketplace_name: str | None = None
    marketplace_domain: str | None = None
    url: str
    title: str | None = None
    image_url: str | None = None
    description: str | None = None
    current_price: float | None = None
    original_price: float | None = None
    currency: str = "USD"
    price_change_pct_24h: float | None = None
    price_change_pct_7d: float | None = None
    price_change_pct_30d: float | None = None
    volatility_30d: float | None = None
    status: str
    last_scraped_at: datetime | None = None

    model_config = {"from_attributes": True}


class GlobalProductListResponse(BaseModel):
    items: list[GlobalProductResponse]
    total: int
    limit: int
    offset: int


class PoolCategorySummary(BaseModel):
    marketplace_domain: str
    marketplace_name: str | None = None
    product_count: int
    avg_price: float | None = None


class PoolStatsResponse(BaseModel):
    total_products: int
    total_marketplaces: int
    products_with_price: int
    last_discovery_at: datetime | None = None
