"""Pure assembly of KPI history series from grouped reads (no DB)."""

from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from app.modules.visualisation_calc.kpi_history.schemas import (
    KpiHistoryPoint,
    KpiHistoryResponse,
    KpiHistorySeries,
)

_PCT_QUANT = Decimal("0.0001")


def build_kpi_history(
    price_rows: list[tuple[date, int, int, Decimal | None]],
    pool_before: int,
    pool_entries: list[tuple[date, int]],
    *,
    days: int,
) -> KpiHistoryResponse:
    """total_pool is a running sum over pool-entry days; the price-derived
    series carry only days that actually had scrape activity."""
    updated = [
        KpiHistoryPoint(date=day, value=Decimal(count))
        for day, count, _, _ in price_rows
    ]
    changed = [
        KpiHistoryPoint(date=day, value=Decimal(count))
        for day, _, count, _ in price_rows
    ]
    volatility = [
        KpiHistoryPoint(date=day, value=avg.quantize(_PCT_QUANT, rounding=ROUND_HALF_UP))
        for day, _, _, avg in price_rows
        if avg is not None
    ]

    running = pool_before
    total_pool: list[KpiHistoryPoint] = []
    for day, added in pool_entries:
        running += added
        total_pool.append(KpiHistoryPoint(date=day, value=Decimal(running)))

    return KpiHistoryResponse(
        days=days,
        series=KpiHistorySeries(
            total_pool=total_pool,
            updated_24h=updated,
            changed_gt5=changed,
            avg_volatility=volatility,
        ),
    )
