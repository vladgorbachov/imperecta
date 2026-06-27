"""Compute the average-price trend over time (pure assembly, no DB)."""

from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

from app.modules.visualisation_calc.trend.schemas import TrendPoint, TrendSeries


def _format_bucket_label(bucket_start: date, bucket: Literal["day", "week", "month"]) -> str:
    if bucket == "day":
        return bucket_start.isoformat()
    if bucket == "week":
        iso = bucket_start.isocalendar()
        return f"{iso.year}-W{iso.week:02d}"
    return f"{bucket_start.year}-{bucket_start.month:02d}"


def _quantize_eur(value: Decimal | None) -> Decimal | None:
    if value is None:
        return None
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def build_trend_series(
    rows: list[tuple[date, Decimal | None, int]],
    *,
    period: Literal["7d", "30d", "90d"],
    bucket: Literal["day", "week", "month"],
) -> TrendSeries:
    """Map grouped read rows into the trend response (no fabrication)."""
    points = [
        TrendPoint(
            bucket_label=_format_bucket_label(bucket_start, bucket),
            bucket_start=bucket_start,
            avg_price_eur=_quantize_eur(avg_price_eur),
            sample_size=sample_size,
        )
        for bucket_start, avg_price_eur, sample_size in rows
    ]
    buckets_with_data = sum(1 for point in points if point.sample_size > 0)
    return TrendSeries(
        points=points,
        currency="EUR",
        bucket=bucket,
        period=period,
        data_ready=buckets_with_data >= 2,
    )
