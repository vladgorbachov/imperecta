"""Response schemas for pool average-price trend series."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel


class TrendPoint(BaseModel):
    bucket_label: str
    bucket_start: date
    avg_price_eur: Decimal | None
    sample_size: int


class TrendSeries(BaseModel):
    points: list[TrendPoint]
    currency: Literal["EUR"] = "EUR"
    bucket: Literal["day", "week", "month"]
    period: Literal["7d", "30d", "90d"]
    data_ready: bool
