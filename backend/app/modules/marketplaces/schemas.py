"""Schemas for marketplace management (admin, dim_marketplace)."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class MarketplaceCreateByUrl(BaseModel):
    url: str
    country_code: str = Field(..., min_length=2, max_length=2)


class MarketplaceUpdate(BaseModel):
    """Partial update for admin marketplace CRUD."""

    name: str | None = Field(None, min_length=1, max_length=200)
    url: str | None = Field(None, min_length=1, max_length=2048)
    is_active: bool | None = None
    country_code: str | None = Field(None, min_length=2, max_length=2)


class CountryRef(BaseModel):
    """Active dim_country row for admin marketplace country picker."""

    code: str
    name: str
    name_local: str | None = None
    region: str
    currency_code: str


class AdminMarketplaceListItem(BaseModel):
    """Shape returned by /admin/marketplaces (list/add/update mutations).

    Real scrape statistics (success_rate, total_runs, last_error_message, ...)
    live on a separate endpoint, /admin/parsing/marketplaces-detailed, which
    aggregates ScrapeLog into the rich Parsing Admin view. This list/CRUD
    response intentionally carries only identity, location, and the latest
    raw scrape ping; it does not fabricate zeroed statistics (Rule 3).
    """

    marketplace_id: str
    name: str
    domain: str
    country_code: str
    country: str
    region: str = ""
    source: Literal["registry", "admin"] = "admin"
    is_active: bool
    last_scrape_at: datetime | None = None
    last_scrape_status: Literal["success", "error", "timeout", "blocked"] | None = None
    products_count: int = 0

    model_config = {"from_attributes": False}
