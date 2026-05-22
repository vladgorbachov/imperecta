"""Schemas for product pool (listings tied to dim_product / dim_marketplace)."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class PoolRecentPricePoint(BaseModel):
    """Recent historical price point for sparkline rendering."""

    date: str
    price: float
    currency: str


class PoolProductItem(BaseModel):
    """Single row in the pool: listing + product + marketplace context."""

    id: UUID
    product_id: UUID
    title: str | None = None
    image_url: str | None = None
    url: str | None = None
    marketplace_name: str | None = None
    marketplace_domain: str | None = None
    marketplace_code: str | None = None
    country_code: str | None = None
    price: float | None = None
    currency: str | None = None
    price_eur: float | None = None
    price_change_pct: float | None = None
    in_stock: bool | None = None
    last_checked_at: datetime | None = None
    status: str | None = None
    is_active: bool | None = None
    recent_prices: list[PoolRecentPricePoint] = []

    model_config = {"from_attributes": True}


class PoolProductsResponse(BaseModel):
    items: list[PoolProductItem]
    total: int
    limit: int
    offset: int


class PoolStatsResponse(BaseModel):
    total_products: int
    total_listings: int
    marketplaces_count: int
    listings_with_price: int
    last_updated: datetime | None = None
    # Legacy keys (optional) for older clients / stubs
    total_marketplaces: int | None = None
    products_with_price: int | None = None
    last_discovery_at: datetime | None = None
    message: str | None = None


class MarketplaceStatsItem(BaseModel):
    marketplace_id: UUID
    marketplace_name: str
    marketplace_domain: str
    country_code: str
    listing_count: int


class PoolCategoriesResponse(BaseModel):
    marketplaces: list[MarketplaceStatsItem]


class PoolCategorySummary(BaseModel):
    """Legacy shape for GET /pool/marketplace-stats."""

    marketplace_domain: str
    marketplace_name: str | None = None
    product_count: int
    avg_price: float | None = None


