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
