"""Competitor schemas."""

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

# Marketplace ID: any string. No special treatment for specific marketplaces.
MarketplaceType = str


class CompetitorCreate(BaseModel):
    """Schema for competitor creation."""

    name: str = Field(..., max_length=200)
    website_url: str | None = None
    marketplace: MarketplaceType
    notes: str | None = None


class CompetitorUpdate(BaseModel):
    """Schema for competitor update - all fields optional."""

    name: str | None = Field(None, max_length=200)
    website_url: str | None = None
    marketplace: MarketplaceType | None = None
    notes: str | None = None


class CompetitorResponse(BaseModel):
    """Schema for competitor response."""

    id: UUID
    user_id: UUID
    name: str
    website_url: str | None
    marketplace: str
    notes: str | None
    created_at: datetime
    product_count: int = 0

    class Config:
        from_attributes = True


class CompetitorProductCreate(BaseModel):
    """Schema for competitor product creation."""

    product_id: UUID
    competitor_id: UUID
    url: str
    name: str | None = Field(None, max_length=500)
    scraper_type: str = Field(default="auto", max_length=20)
    css_selector_price: str | None = Field(None, max_length=500)


class CompetitorProductResponse(BaseModel):
    """Schema for competitor product response with price diff."""

    id: UUID
    product_id: UUID
    competitor_id: UUID
    competitor_name: str
    url: str
    name: str | None
    last_price: Decimal | None
    last_promo_label: str | None
    last_in_stock: bool | None
    last_checked_at: datetime | None
    scraper_type: str
    css_selector_price: str | None
    is_active: bool
    created_at: datetime
    price_diff: float | None = None  # % difference from user product price

    class Config:
        from_attributes = True
