"""Schemas for market data: forex, crypto, commodities, fuel, ticker, preferences."""

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


# --- User dashboard preferences (stored in users.preferences JSONB) ---


class UserPreferencesResponse(BaseModel):
    preferred_country_code: str | None = None
    dashboard_widgets: list[str] = Field(default_factory=list)
    forex_favorites: list[str] = Field(default_factory=list)
    crypto_favorites: list[str] = Field(default_factory=list)
    commodity_favorites: list[str] = Field(default_factory=list)
    favorite_instrument_ids: list[str] = Field(
        default_factory=list,
        description="Legacy aggregated favorites for ticker widgets",
    )


class UserPreferencesUpdate(BaseModel):
    preferred_country_code: str | None = None
    dashboard_widgets: list[str] | None = None
    forex_favorites: list[str] | None = None
    crypto_favorites: list[str] | None = None
    commodity_favorites: list[str] | None = None
    favorite_instrument_ids: list[str] | None = Field(None, max_length=50)


class MarketsPreferencesResponse(UserPreferencesResponse):
    """GET/PUT /markets/preferences response."""


class MarketsPreferencesUpdate(UserPreferencesUpdate):
    """PUT /markets/preferences body."""


# --- Refresh metadata (legacy list shape for API) ---


class MarketsRefreshStatusItem(BaseModel):
    refresh_type: str
    last_successful_refresh: datetime | None = None
    last_failed_refresh: datetime | None = None
    provider_source: str | None = None
    country_scope: str | None = None
    error_message: str | None = None


class MarketsRefreshMetadataResponse(BaseModel):
    items: list[MarketsRefreshStatusItem]


class RefreshMetadataResponse(BaseModel):
    """Alternative grouped metadata (optional future use)."""

    forex: dict[str, Any] | None = None
    crypto: dict[str, Any] | None = None
    commodities: dict[str, Any] | None = None
    fuel: dict[str, Any] | None = None


# --- Forex (existing API shape) ---


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


class ForexRateItem(BaseModel):
    currency_code: str
    rate_to_eur: float
    rate_to_usd: float
    source: str
    fetched_at: datetime


class ForexResponse(BaseModel):
    items: list[ForexRateItem]
    base: str = "EUR"


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


class CryptoItem(BaseModel):
    symbol: str
    name: str | None = None
    price_usd: float
    price_eur: float | None = None
    market_cap_usd: float | None = None
    volume_24h_usd: float | None = None
    change_24h_pct: float | None = None
    change_7d_pct: float | None = None
    rank: int | None = None
    source: str = ""


class CryptoResponse(BaseModel):
    items: list[CryptoItem]


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


class CommodityItem(BaseModel):
    symbol: str
    name: str
    commodity_type: str
    price_usd: float
    price_eur: float | None = None
    change_24h_pct: float | None = None
    unit: str
    source: str


class CommoditiesResponse(BaseModel):
    items: list[CommodityItem]
    error: str | None = None


# --- Fuel ---


class FuelPriceItem(BaseModel):
    fuel_type: str
    price_local: float
    currency_code: str
    price_eur: float | None = None
    change_week_pct: float | None = None


class FuelResponse(BaseModel):
    country_code: str
    items: list[FuelPriceItem]


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


class TickerItem(BaseModel):
    symbol: str
    name: str | None = None
    price: float
    change_pct: float | None = None
    type: str  # forex, crypto, commodity, fuel


class TickerResponse(BaseModel):
    items: list[TickerItem]
    country: str
