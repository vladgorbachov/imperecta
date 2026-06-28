"""Field assembly for scrape gate UPDATE/DELETE payloads (no validation)."""

from __future__ import annotations

import calendar
from datetime import date
from typing import Any
from uuid import UUID


def build_dim_date_fields(
    *,
    date_id: int,
    full_date: date,
    year: int,
    quarter: int,
    month: int,
    month_name: str,
    week_iso: int,
    day_of_month: int,
    day_of_week: int,
    day_name: str,
    is_weekend: bool,
    is_last_day_of_month: bool,
) -> dict[str, Any]:
    """Full dim_date row for evaluate_market insert."""
    return {
        "date_id": date_id,
        "full_date": full_date,
        "year": year,
        "quarter": quarter,
        "month": month,
        "month_name": month_name,
        "week_iso": week_iso,
        "day_of_month": day_of_month,
        "day_of_week": day_of_week,
        "day_name": day_name,
        "is_weekend": is_weekend,
        "is_last_day_of_month": is_last_day_of_month,
    }


def build_dim_date_fields_from_day(d: date) -> dict[str, Any]:
    """Compute full dim_date insert payload for a calendar day."""
    date_id = int(d.strftime("%Y%m%d"))
    _, iso_week, iso_weekday = d.isocalendar()
    return build_dim_date_fields(
        date_id=date_id,
        full_date=d,
        year=d.year,
        quarter=(d.month - 1) // 3 + 1,
        month=d.month,
        month_name=d.strftime("%B"),
        week_iso=iso_week,
        day_of_month=d.day,
        day_of_week=iso_weekday,
        day_name=d.strftime("%A"),
        is_weekend=iso_weekday >= 6,
        is_last_day_of_month=d.day == calendar.monthrange(d.year, d.month)[1],
    )


def build_listing_update_fields(*, url_hash: str, **delta: Any) -> dict[str, Any]:
    """Locator + changed fact_listing columns for authorize_scrape_update."""
    return {"url_hash": url_hash, **delta}


def build_product_update_fields(*, product_id: UUID | str, **delta: Any) -> dict[str, Any]:
    """Locator + changed dim_product columns for authorize_scrape_update."""
    pid = product_id if isinstance(product_id, str) else str(product_id)
    return {"id": pid, **delta}


def build_listing_delete_fields(*, url_hash: str) -> dict[str, Any]:
    """Locator-only payload for fact_listing DELETE."""
    return {"url_hash": url_hash}


def build_product_delete_fields(*, product_id: UUID | str) -> dict[str, Any]:
    """Locator-only payload for dim_product DELETE."""
    pid = product_id if isinstance(product_id, str) else str(product_id)
    return {"id": pid}
