"""Markets domain Pydantic schemas. Production-grade typed contracts."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# --- Preferences ---


class MarketsPreferencesResponse(BaseModel):
    """User markets preferences."""

    preferred_country_code: str | None
    favorite_instrument_ids: list[str]


class MarketsPreferencesUpdate(BaseModel):
    """Update markets preferences."""

    preferred_country_code: str | None = Field(None, max_length=3)
    favorite_instrument_ids: list[str] | None = Field(None, max_length=50)


# --- Refresh metadata ---


class MarketsRefreshStatusItem(BaseModel):
    """Refresh status for a single data type."""

    refresh_type: str
    last_successful_refresh: datetime | None = None
    last_failed_refresh: datetime | None = None
    provider_source: str | None = None
    country_scope: str | None = None
    error_message: str | None = None


class MarketsRefreshMetadataResponse(BaseModel):
    """Aggregate refresh status for all markets data types."""

    items: list[MarketsRefreshStatusItem]


# --- Forex ---


class MarketsForexItem(BaseModel):
    """Single forex pair for widget."""

    symbol: str
    bid: Decimal
    ask: Decimal
    spread: Decimal
    change_24h: float | None
    refreshed_at: datetime


class MarketsForexResponse(BaseModel):
    """Forex widget data."""

    items: list[MarketsForexItem]
    last_refreshed_at: datetime | None


# --- Crypto ---


class MarketsCryptoItem(BaseModel):
    """Single crypto asset for widget."""

    symbol: str
    price: Decimal
    change_24h: float | None
    market_cap: Decimal | None
    refreshed_at: datetime


class MarketsCryptoResponse(BaseModel):
    """Crypto widget data. Never 503 — returns items=[], error=msg on API failure."""

    items: list[MarketsCryptoItem]
    error: str | None = None
    cached: bool = False
    last_refreshed_at: datetime | None


# --- Commodities ---


class MarketsCommodityItem(BaseModel):
    """Single commodity/resource for widget."""

    symbol: str
    name: str | None
    price: Decimal
    change_24h: float | None
    unit: str | None
    refreshed_at: datetime


class MarketsCommoditiesResponse(BaseModel):
    """Resources/commodities widget data. Never 503 — returns items=[], error=msg on API failure."""

    items: list[MarketsCommodityItem]
    error: str | None = None
    cached: bool = False
    last_refreshed_at: datetime | None


# --- Ticker bar ---


class MarketsTickerItem(BaseModel):
    """Ticker bar item."""

    symbol: str
    name: str | None
    price: Decimal
    change_24h: float | None
    currency: str | None
    refreshed_at: datetime


class MarketsTickerResponse(BaseModel):
    """Ticker bar data."""

    items: list[MarketsTickerItem]
    last_refreshed_at: datetime | None


# --- Market Overview tabbed table ---


class MarketsOverviewItem(BaseModel):
    """Single row for Market Overview table."""

    id: UUID
    marketplace: str
    marketplace_domain: str
    marketplace_id: str | None = None
    product_name: str
    product_url: str | None = None
    price: Decimal
    currency: str
    category: str | None = None
    change_24h: float | None
    change_3d: float | None
    change_1w: float | None
    change_1m: float | None
    sparkline_data: list[float]
    last_updated: datetime


class MarketsOverviewResponse(BaseModel):
    """Market Overview tabbed table data."""

    items: list[MarketsOverviewItem]
    total: int
    sort: str
    last_refreshed_at: datetime | None


# --- Category/segment analytics ---


class MarketsCategoryAnalyticsItem(BaseModel):
    """Category/segment analytics row."""

    id: UUID
    category_id: str
    segment: str | None
    metrics: dict
    refreshed_at: datetime


class MarketsCategoryAnalyticsResponse(BaseModel):
    """Category analytics data."""

    items: list[MarketsCategoryAnalyticsItem]
    last_refreshed_at: datetime | None


# --- Marketplace analytics ---


class MarketsMarketplaceAnalyticsItem(BaseModel):
    """Marketplace analytics row. Separate from competitor-benchmark domain."""

    id: UUID
    marketplace_id: str
    marketplace_name: str | None
    metrics: dict
    refreshed_at: datetime


class MarketsMarketplaceAnalyticsResponse(BaseModel):
    """Marketplace table analytics data."""

    items: list[MarketsMarketplaceAnalyticsItem]
    last_refreshed_at: datetime | None


# --- Opportunity blocks ---


class MarketsOpportunityBlockItem(BaseModel):
    """Opportunity block."""

    id: UUID
    block_type: str
    title: str
    metrics: dict
    refreshed_at: datetime


class MarketsOpportunitiesResponse(BaseModel):
    """Opportunity blocks data."""

    items: list[MarketsOpportunityBlockItem]
    last_refreshed_at: datetime | None
