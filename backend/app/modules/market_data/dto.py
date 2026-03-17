"""Normalized DTOs for market data. Provider-agnostic, used in API responses."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class NormalizedForex(BaseModel):
    """Normalized forex pair. No provider-specific fields."""

    symbol: str = Field(..., max_length=20)
    bid: Decimal = Field(..., ge=0)
    ask: Decimal = Field(..., ge=0)
    spread: Decimal = Field(..., ge=0)
    change_24h: float | None = None
    refreshed_at: datetime


class NormalizedCrypto(BaseModel):
    """Normalized crypto asset. No provider-specific fields."""

    symbol: str = Field(..., max_length=20)
    price: Decimal = Field(..., ge=0)
    change_24h: float | None = None
    market_cap: Decimal | None = None
    refreshed_at: datetime


class NormalizedCommodity(BaseModel):
    """Normalized commodity/resource. No provider-specific fields."""

    symbol: str = Field(..., max_length=20)
    name: str | None = None
    price: Decimal = Field(..., ge=0)
    change_24h: float | None = None
    unit: str | None = None
    refreshed_at: datetime
