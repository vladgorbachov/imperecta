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
