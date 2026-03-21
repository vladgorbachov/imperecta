"""Schemas for marketplace management (admin, dim_marketplace)."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


class MarketplaceResponse(BaseModel):
    id: UUID
    marketplace_code: str
    name: str
    source_type: str
    country_code: str
    domain: str
    base_url: str
    currency_code: str
    is_active: bool
    reliability_score: float | None = None
    last_scrape_at: datetime | None = None
    last_scrape_status: str | None = None
    product_quota: int = 0
    products_in_pool: int = 0
    requires_js: bool = False
    rate_limit_delay: Decimal | None = None
    last_discovery_at: datetime | None = None
    last_discovery_status: str | None = None
    last_discovery_products_found: int | None = None
    discovery_error_count: int | None = None

    model_config = {"from_attributes": True}


class MarketplaceCreateByUrl(BaseModel):
    url: str


class MarketplaceListResponse(BaseModel):
    items: list[MarketplaceResponse]
    total: int
