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


class CoverageBreakdown(BaseModel):
    """Grouped listing counts over the visible product pool."""

    mode: Literal["countries", "marketplaces"]
    rows: list[CoverageRow]
    total: int
