"""Market data schemas."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class MarketsPreferencesResponse(BaseModel):
    preferred_country_code: str | None
    favorite_instrument_ids: list[str]


class MarketsPreferencesUpdate(BaseModel):
    preferred_country_code: str | None = Field(None, max_length=3)
    favorite_instrument_ids: list[str] | None = Field(None, max_length=50)


class MarketsRefreshStatusItem(BaseModel):
    refresh_type: str
    last_successful_refresh: datetime | None = None
    last_failed_refresh: datetime | None = None
    provider_source: str | None = None
    country_scope: str | None = None
    error_message: str | None = None


class MarketsRefreshMetadataResponse(BaseModel):
    items: list[MarketsRefreshStatusItem]


class MarketsForexItem(BaseModel):
    symbol: str
    bid: Decimal
    ask: Decimal
    spread: Decimal
    change_24h: float | None
    refreshed_at: datetime


class MarketsForexResponse(BaseModel):
    items: list[MarketsForexItem]
    last_refreshed_at: datetime | None


class MarketsCryptoItem(BaseModel):
    symbol: str
    price: Decimal
    change_24h: float | None
    market_cap: Decimal | None
    refreshed_at: datetime


class MarketsCryptoResponse(BaseModel):
    items: list[MarketsCryptoItem]
    error: str | None = None
    cached: bool = False
    last_refreshed_at: datetime | None


class MarketsCommodityItem(BaseModel):
    symbol: str
    name: str | None
    price: Decimal
    change_24h: float | None
    unit: str | None
    refreshed_at: datetime


class MarketsCommoditiesResponse(BaseModel):
    items: list[MarketsCommodityItem]
    error: str | None = None
    cached: bool = False
    last_refreshed_at: datetime | None


class MarketsTickerItem(BaseModel):
    symbol: str
    name: str | None
    price: Decimal
    change_24h: float | None
    currency: str | None
    refreshed_at: datetime


class MarketsTickerResponse(BaseModel):
    items: list[MarketsTickerItem]
    last_refreshed_at: datetime | None
