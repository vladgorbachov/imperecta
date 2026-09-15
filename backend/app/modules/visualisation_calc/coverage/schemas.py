"""Response schemas for geographic pool coverage breakdown."""

from __future__ import annotations

from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class CoverageRow(BaseModel):
    """One row in a country roll-up or per-country marketplace breakdown."""

    key: str
    label: str
    country_code: str | None = None
    marketplace_id: UUID | None = None
    marketplace_domain: str | None = None
    count: int
    share_pct: Decimal | None = None
    # World mode (Zone D) only — None elsewhere:
    avg_price_eur: Decimal | None = None
    movers_rate_pct: Decimal | None = None


class CoverageBreakdown(BaseModel):
    """Grouped listing counts over the visible product pool."""

    mode: Literal["countries", "marketplaces"]
    rows: list[CoverageRow]
    total: int
    # World mode (Zone C/D) only — share_pct uses the grand pool denominator
    # and these carry the pool benchmark; None elsewhere:
    pool_total: int | None = None
    pool_avg_price_eur: Decimal | None = None
    pool_movers_rate_pct: Decimal | None = None
