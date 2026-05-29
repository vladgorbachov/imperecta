"""Schemas for marketplace management (admin, dim_marketplace)."""

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


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
    avg_response_ms: int | None = None
    last_scrape_at: datetime | None = None
    last_scrape_status: str | None = None
    logo_url: str | None = None
    monthly_visits: int | None = None
    product_quota: int = 0
    products_in_pool: int = 0
    requires_js: bool = False
    rate_limit_delay: Decimal | None = None
    last_discovery_at: datetime | None = None
    last_discovery_status: str | None = None
    last_discovery_products_found: int = 0
    discovery_error_count: int = 0

    model_config = {"from_attributes": True}


class MarketplaceCreateByUrl(BaseModel):
    url: str


class MarketplaceUpdate(BaseModel):
    """Partial update for admin marketplace CRUD."""

    name: str | None = Field(None, min_length=1, max_length=200)
    url: str | None = Field(None, min_length=1, max_length=2048)
    is_active: bool | None = None


class MarketplaceListResponse(BaseModel):
    items: list[MarketplaceResponse]
    total: int


class ImportTextBody(BaseModel):
    content: str = Field(..., min_length=1)


class SetRequiresJsBody(BaseModel):
    marketplace_id: UUID
    requires_js: bool = False


class AdminMarketplaceListItem(BaseModel):
    """Shape expected by the admin UI (legacy field names)."""

    marketplace_id: str
    name: str
    domain: str
    country: str
    region: str = ""
    source: Literal["registry", "admin"] = "admin"
    is_active: bool
    last_scrape_at: datetime | None = None
    last_scrape_status: Literal["success", "error", "timeout", "blocked"] | None = None
    last_error: str | None = None
    total_scrapes: int = 0
    successful_scrapes: int = 0
    failed_scrapes: int = 0
    success_rate: float = 0.0
    products_count: int = 0

    model_config = {"from_attributes": False}
