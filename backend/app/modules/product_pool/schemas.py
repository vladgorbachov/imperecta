"""Schemas for product pool (listings tied to dim_product / dim_marketplace)."""

import datetime as dt
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class PoolRecentPricePoint(BaseModel):
    """Recent historical price point for sparkline rendering."""

    date: str
    price: float
    currency: str


class LocalCurrencyResolution(BaseModel):
    """How the marketplace's local currency was determined for display."""

    currency: str | None = None
    source: str = "unknown"


class PoolProductItem(BaseModel):
    """Single row in the pool: listing + product + marketplace context.

    Canonical field names: `price`, `last_checked_at`, `price_change_pct`.
    PP1 removed the duplicate legacy names (current_price, last_scraped_at,
    price_change_pct_24h) and the always-None placeholders
    (original_price, price_change_pct_7d/30d, volatility_30d). Real
    multi-window analytics will be reborn with the analytics layer.
    """

    id: UUID
    product_id: UUID
    title: str | None = None
    image_url: str | None = None
    url: str | None = None
    marketplace_id: UUID | None = None
    marketplace_name: str | None = None
    marketplace_domain: str | None = None
    marketplace_code: str | None = None
    country_code: str | None = None
    # P10: taxonomy labels on the list grain (null until extraction matures).
    brand: str | None = None
    category: str | None = None
    # P13: type + universal-language (EN) layer; null until enrichment fills.
    product_type: str | None = None
    product_type_en: str | None = None
    category_en: str | None = None
    title_en: str | None = None
    price: float | None = None
    currency: str | None = None
    price_eur: float | None = None
    display_price: float | None = None
    display_currency: str | None = None
    conversion_available: bool = False
    local_currency_resolution: LocalCurrencyResolution | None = None
    local_currency_unavailable: bool = False
    price_change_pct: float | None = None
    last_checked_at: datetime | None = None
    status: str | None = None
    is_active: bool | None = None
    recent_prices: list[PoolRecentPricePoint] = []

    model_config = {"from_attributes": True}


class PoolProductsResponse(BaseModel):
    """Shared envelope for /pool/products and /markets/overview.

    P12: total may be an estimate (mv_pool_stats or capped count);
    next_cursor/prev_cursor enable keyset paging for keyset-capable sorts.
    With skip_total=true the count is not computed at all and total is null
    (typeahead callers ignore totals).
    """

    items: list[PoolProductItem]
    total: int | None
    limit: int
    offset: int
    total_is_estimate: bool = False
    next_cursor: str | None = None
    prev_cursor: str | None = None


class PoolStatsResponse(BaseModel):
    """Aggregate counts for the global pool dashboard card."""

    total_products: int
    total_listings: int
    marketplaces_count: int
    listings_with_price: int
    last_updated: datetime | None = None


class PoolCategoryItem(BaseModel):
    """Row of /pool/categories: a marketplace browseable as a category."""

    marketplace_id: str
    marketplace_code: str
    name: str
    domain: str
    country_code: str | None = None
    listing_count: int


class PoolCategorySummary(BaseModel):
    """Row of /pool/marketplace-stats: marketplace summary with avg price."""

    marketplace_domain: str
    marketplace_name: str | None = None
    country_code: str | None = None
    product_count: int
    avg_price: float | None = None


class PoolProductDetail(PoolProductItem):
    """Full product card for /pool/products/{listing_id} (P2).

    brand/category are inherited from the list item since P10.
    """

    description: str | None = None
    attributes: dict | None = None


class PriceHistoryPoint(BaseModel):
    date: dt.date
    price: float | None = None
    price_eur: float | None = None


class PriceHistoryResponse(BaseModel):
    """Daily price series for one listing (P1). Honest empty under 2 buckets."""

    listing_id: UUID
    currency: str | None = None
    period: Literal["7d", "30d", "90d"]
    points: list[PriceHistoryPoint]
    data_ready: bool
