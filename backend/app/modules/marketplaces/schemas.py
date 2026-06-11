"""Schemas for marketplace management (admin, dim_marketplace)."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class MarketplaceCreateByUrl(BaseModel):
    url: str


class MarketplaceUpdate(BaseModel):
    """Partial update for admin marketplace CRUD."""

    name: str | None = Field(None, min_length=1, max_length=200)
    url: str | None = Field(None, min_length=1, max_length=2048)
    is_active: bool | None = None


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
    country: str
    region: str = ""
    source: Literal["registry", "admin"] = "admin"
    is_active: bool
    last_scrape_at: datetime | None = None
    last_scrape_status: Literal["success", "error", "timeout", "blocked"] | None = None
    products_count: int = 0

    model_config = {"from_attributes": False}
