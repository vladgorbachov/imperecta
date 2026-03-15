"""Product schemas."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class ProductCreate(BaseModel):
    """Schema for product creation."""

    name: str = Field(..., max_length=500)
    sku: str | None = Field(None, max_length=100)
    current_price: Decimal = Field(..., ge=0)
    currency: str = Field(default="RUB", max_length=10)
    url: str | None = None
    category: str | None = Field(None, max_length=200)


class ProductUpdate(BaseModel):
    """Schema for product update - all fields optional."""

    name: str | None = Field(None, max_length=500)
    sku: str | None = Field(None, max_length=100)
    current_price: Decimal | None = Field(None, ge=0)
    currency: str | None = Field(None, max_length=10)
    url: str | None = None
    category: str | None = Field(None, max_length=200)
    is_active: bool | None = None


class ProductResponse(BaseModel):
    """Schema for product response with competitor count."""

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
    """Product list item with competitor price aggregates."""

    min_competitor_price: Decimal | None = None
    max_competitor_price: Decimal | None = None
    last_checked_at: datetime | None = None


class ProductListResponse(BaseModel):
    """Schema for paginated product list."""

    items: list[ProductListItem]
    total: int


class CompetitorProductBrief(BaseModel):
    """Brief competitor product info for product detail."""

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
    """Product with full details and competitor products list."""

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
