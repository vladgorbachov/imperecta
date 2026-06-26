"""Contracts for price-movement widget payloads (consumer of fact_price.price_change_pct)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class LocalCurrencyResolution(BaseModel):
    """How the marketplace's local currency was determined for display."""

    currency: str | None = None
    source: str = "unknown"


class MoverItem(BaseModel):
    """Single listing that moved beyond the configured threshold."""

    product_name: str
    image_url: str | None = None
    marketplace_name: str
    marketplace_domain: str | None = None
    country_code: str
    old_price: Decimal | None
    new_price: Decimal
    currency: str
    price_change_pct: Decimal
    direction: Literal["up", "down"]
    changed_at: datetime
    old_price_reconstructed: bool = False
    display_old_price: Decimal | None = None
    display_new_price: Decimal | None = None
    display_currency: str | None = None
    conversion_available: bool = False
    local_currency_resolution: LocalCurrencyResolution | None = None
    local_currency_unavailable: bool = False


class MoversPage(BaseModel):
    """Paginated movers feed."""

    items: list[MoverItem]
    total: int
    limit: int
    offset: int
    has_more: bool


class MoversSummaryBucket(BaseModel):
    """One histogram bucket for abs(price_change_pct)."""

    label: str
    min_pct: Decimal
    max_pct: Decimal | None
    count: int


class MoversSummary(BaseModel):
    """Aggregate movement stats for the selected window."""

    up_count: int
    down_count: int
    unchanged_count: int
    biggest_gainer: MoverItem | None
    biggest_loser: MoverItem | None
    avg_abs_change: Decimal | None
    buckets: list[MoversSummaryBucket]


class MoversCoverageMeta(BaseModel):
    """Honest data-accumulation signal for thin databases."""

    listings_with_change: int
    listings_total: int
    data_ready: bool


class MoversKpi(BaseModel):
    """>N% movers KPI count."""

    count: int


class MovementsFilters(BaseModel):
    """Shared filter contract for movements reads and calc."""

    country_code: str | None = None
    period: Literal["24h", "7d", "30d"] = "24h"
    marketplace_id: UUID | None = None
    category_id: UUID | None = None
    direction: Literal["up", "down", "all"] = "all"
    threshold: Decimal = Field(default=Decimal("5.0"))
    limit: int = Field(default=20, ge=1, le=200)
    offset: int = Field(default=0, ge=0)
    sort_by: Literal["abs_change", "changed_at"] = "abs_change"
