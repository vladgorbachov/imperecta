"""Compute geographic pool coverage: country roll-up and per-country marketplace breakdown."""

from __future__ import annotations

from collections.abc import Sequence
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from app.modules.visualisation_calc.coverage.schemas import CoverageBreakdown, CoverageRow


def _share_pct(count: int, total: int) -> Decimal | None:
    if total <= 0:
        return None
    return (
        Decimal(count) / Decimal(total) * Decimal(100)
    ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def build_country_rollup(rows: Sequence[tuple[str, str, int]]) -> CoverageBreakdown:
    """Pack country roll-up counts with share of grand total (pure, no DB)."""
    total = sum(count for _, _, count in rows)
    if total <= 0:
        return CoverageBreakdown(mode="countries", rows=[], total=0)

    breakdown_rows = [
        CoverageRow(
            key=country_code,
            label=country_name,
            country_code=country_code,
            count=count,
            share_pct=_share_pct(count, total),
        )
        for country_code, country_name, count in rows
    ]
    return CoverageBreakdown(mode="countries", rows=breakdown_rows, total=total)


def build_marketplace_breakdown(
    rows: Sequence[tuple[UUID, str, str | None, int]],
) -> CoverageBreakdown:
    """Pack per-marketplace counts within a country (pure, no DB)."""
    total = sum(count for _, _, _, count in rows)
    if total <= 0:
        return CoverageBreakdown(mode="marketplaces", rows=[], total=0)

    breakdown_rows = [
        CoverageRow(
            key=str(marketplace_id),
            label=name,
            marketplace_id=marketplace_id,
            marketplace_domain=domain,
            count=count,
            share_pct=_share_pct(count, total),
        )
        for marketplace_id, name, domain, count in rows
    ]
    return CoverageBreakdown(mode="marketplaces", rows=breakdown_rows, total=total)


def build_world_marketplace_breakdown(
    rows: Sequence[tuple[UUID, str, str | None, int]],
    *,
    world_stats: Sequence[tuple[UUID, Decimal | None, int, int]],
    pool_total: int,
    pool_avg_price_eur: Decimal | None,
    pool_movers: int,
) -> CoverageBreakdown:
    """World (ZZ) mode: each global shop benchmarked against the GRAND pool.

    share_pct uses the grand pool denominator (a global shop's weight in the
    whole pool, Zone C); avg_price_eur and movers_rate_pct come as rates per
    shop next to the pool benchmark (Zone D) — never absolute comparisons,
    global shops differ in size.
    """
    stats_by_id = {mp_id: (avg, movers, count) for mp_id, avg, movers, count in world_stats}
    subtotal = sum(count for _, _, _, count in rows)

    breakdown_rows = []
    for marketplace_id, name, domain, count in rows:
        avg_price, movers, stat_count = stats_by_id.get(marketplace_id, (None, 0, 0))
        breakdown_rows.append(
            CoverageRow(
                key=str(marketplace_id),
                label=name,
                marketplace_id=marketplace_id,
                marketplace_domain=domain,
                count=count,
                share_pct=_share_pct(count, pool_total),
                avg_price_eur=(
                    avg_price.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                    if avg_price is not None
                    else None
                ),
                movers_rate_pct=_share_pct(movers, stat_count),
            )
        )
    return CoverageBreakdown(
        mode="marketplaces",
        rows=breakdown_rows,
        total=subtotal,
        pool_total=pool_total,
        pool_avg_price_eur=(
            pool_avg_price_eur.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            if pool_avg_price_eur is not None
            else None
        ),
        pool_movers_rate_pct=_share_pct(pool_movers, pool_total),
    )
