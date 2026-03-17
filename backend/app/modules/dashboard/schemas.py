"""Dashboard analytics schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class MarketsCategoryAnalyticsItem(BaseModel):
    id: UUID
    category_id: str
    segment: str | None
    metrics: dict
    refreshed_at: datetime


class MarketsCategoryAnalyticsResponse(BaseModel):
    items: list[MarketsCategoryAnalyticsItem]
    last_refreshed_at: datetime | None


class MarketsMarketplaceAnalyticsItem(BaseModel):
    id: UUID
    marketplace_id: str
    marketplace_name: str | None
    metrics: dict
    refreshed_at: datetime


class MarketsMarketplaceAnalyticsResponse(BaseModel):
    items: list[MarketsMarketplaceAnalyticsItem]
    last_refreshed_at: datetime | None


class MarketsOpportunityBlockItem(BaseModel):
    id: UUID
    block_type: str
    title: str
    metrics: dict
    refreshed_at: datetime


class MarketsOpportunitiesResponse(BaseModel):
    items: list[MarketsOpportunityBlockItem]
    last_refreshed_at: datetime | None
