"""Schemas for market data: forex, crypto, commodities, ticker, preferences."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


# --- User dashboard preferences (stored in users.preferences JSONB) ---


class UserPreferencesResponse(BaseModel):
    dashboard_widgets: list[str] = Field(default_factory=list)
    forex_favorites: list[str] = Field(default_factory=list)
    crypto_favorites: list[str] = Field(default_factory=list)
    commodity_favorites: list[str] = Field(default_factory=list)
    favorite_instrument_ids: list[str] = Field(
        default_factory=list,
        description="Legacy aggregated favorites for ticker widgets",
    )


class UserPreferencesUpdate(BaseModel):
    dashboard_widgets: list[str] | None = None
    forex_favorites: list[str] | None = None
    crypto_favorites: list[str] | None = None
    commodity_favorites: list[str] | None = None
    favorite_instrument_ids: list[str] | None = Field(None, max_length=50)


class MarketsPreferencesResponse(UserPreferencesResponse):
    """GET/PUT /markets/preferences response."""


class MarketsPreferencesUpdate(UserPreferencesUpdate):
    """PUT /markets/preferences body."""


class MarketsInstrumentOption(BaseModel):
    symbol: str
    name: str | None = None
    rank: int | None = None
    category: str | None = None
    market_cap_usd: float | None = None


class MarketsInstrumentsResponse(BaseModel):
    forex: list[MarketsInstrumentOption] = Field(default_factory=list)
    crypto: list[MarketsInstrumentOption] = Field(default_factory=list)
    commodities: list[MarketsInstrumentOption] = Field(default_factory=list)


# --- Refresh metadata (list shape returned by /markets/refresh-metadata) ---


class MarketsRefreshStatusItem(BaseModel):
    refresh_type: str
    last_successful_refresh: datetime | None = None
    last_failed_refresh: datetime | None = None
    provider_source: str | None = None
    country_scope: str | None = None
    error_message: str | None = None


class MarketsRefreshMetadataResponse(BaseModel):
    items: list[MarketsRefreshStatusItem]


# --- Forex ---


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


# --- Crypto ---


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


# --- Commodities ---


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


# --- Ticker ---


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
