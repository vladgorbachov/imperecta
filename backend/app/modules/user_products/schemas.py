"""User products schemas."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class ProductCreate(BaseModel):
    name: str = Field(..., max_length=500)
    sku: str | None = Field(None, max_length=100)
    current_price: Decimal = Field(..., ge=0)
    currency: str = Field(..., max_length=10)
    url: str | None = None
    category: str | None = Field(None, max_length=200)


class ProductUpdate(BaseModel):
    name: str | None = Field(None, max_length=500)
    sku: str | None = Field(None, max_length=100)
    current_price: Decimal | None = Field(None, ge=0)
    currency: str | None = Field(None, max_length=10)
    url: str | None = None
    category: str | None = Field(None, max_length=200)
    is_active: bool | None = None


class ProductResponse(BaseModel):
    id: UUID
    user_id: UUID
    name: str
    sku: str | None
    current_price: Decimal
    currency: str
    url: str | None
    category: str | None
    is_active: bool
    competitor_count: int = 0
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ProductListItem(ProductResponse):
    min_competitor_price: Decimal | None = None
    max_competitor_price: Decimal | None = None
    last_checked_at: datetime | None = None


class ProductListResponse(BaseModel):
    items: list[ProductListItem]
    total: int


class CompetitorProductBrief(BaseModel):
    id: UUID
    competitor_id: UUID
    competitor_name: str
    marketplace: str
    url: str
    name: str | None
    last_price: Decimal | None
    last_promo_label: str | None = None
    last_in_stock: bool | None = None
    last_checked_at: datetime | None

    class Config:
        from_attributes = True


class ProductDetailResponse(BaseModel):
    id: UUID
    user_id: UUID
    name: str
    sku: str | None
    current_price: Decimal
    currency: str
    url: str | None
    category: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    competitor_products: list[CompetitorProductBrief] = []

    class Config:
        from_attributes = True


MarketplaceType = str


class CompetitorCreate(BaseModel):
    name: str = Field(..., max_length=200)
    website_url: str | None = None
    marketplace: MarketplaceType
    notes: str | None = None


class CompetitorUpdate(BaseModel):
    name: str | None = Field(None, max_length=200)
    website_url: str | None = None
    marketplace: MarketplaceType | None = None
    notes: str | None = None


class CompetitorResponse(BaseModel):
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
    product_id: UUID
    competitor_id: UUID
    url: str
    name: str | None = Field(None, max_length=500)
    scraper_type: str = Field(..., max_length=20)
    css_selector_price: str | None = Field(None, max_length=500)


class CompetitorProductResponse(BaseModel):
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
    price_diff: float | None = None

    class Config:
        from_attributes = True
