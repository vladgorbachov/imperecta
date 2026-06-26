"""MovementsCalc — pure consumer over typed read rows (no DB access)."""

from __future__ import annotations

from collections.abc import Sequence
from decimal import ROUND_HALF_UP, Decimal

from app.modules.visualisation_calc.movements.read import MoverReadRow, MoversCoverageCounts
from app.modules.visualisation_calc.movements.schemas import (
    MoverItem,
    MovementsFilters,
    MoversCoverageMeta,
    MoversKpi,
    MoversPage,
    MoversSummary,
    MoversSummaryBucket,
)

_PRICE_QUANT = Decimal("0.01")
_ZERO = Decimal("0")
_SUMMARY_BUCKETS: tuple[tuple[str, Decimal, Decimal | None], ...] = (
    ("0–5%", Decimal("0"), Decimal("5")),
    ("5–10%", Decimal("5"), Decimal("10")),
    ("10–20%", Decimal("10"), Decimal("20")),
    ("20%+", Decimal("20"), None),
)


def _resolve_old_price(row: MoverReadRow) -> tuple[Decimal | None, bool]:
    """Prefer the actual prior fact_price row; otherwise reconstruct from pct."""
    if row.prior_fact_price is not None:
        return row.prior_fact_price, False

    divisor = Decimal("1") + (row.price_change_pct / Decimal("100"))
    if divisor == 0:
        return None, True
    reconstructed = (row.new_price / divisor).quantize(_PRICE_QUANT, rounding=ROUND_HALF_UP)
    return reconstructed, True


def _direction_for(pct: Decimal) -> str:
    return "up" if pct > 0 else "down"


def _row_to_mover_item(row: MoverReadRow) -> MoverItem:
    old_price, reconstructed = _resolve_old_price(row)
    return MoverItem(
        product_name=row.product_name,
        image_url=row.image_url,
        marketplace_name=row.marketplace_name,
        country_code=row.country_code,
        old_price=old_price,
        new_price=row.new_price,
        currency=row.currency_code,
        price_change_pct=row.price_change_pct,
        direction=_direction_for(row.price_change_pct),
        changed_at=row.changed_at,
        old_price_reconstructed=reconstructed,
    )


def _matches_direction(pct: Decimal, direction: str) -> bool:
    if direction == "all":
        return True
    if direction == "up":
        return pct > 0
    return pct < 0


def _matches_threshold(pct: Decimal, threshold: Decimal) -> bool:
    return abs(pct) >= threshold


def _sort_rows(rows: Sequence[MoverReadRow], sort_by: str) -> list[MoverReadRow]:
    if sort_by == "changed_at":
        return sorted(rows, key=lambda row: row.changed_at, reverse=True)
    return sorted(rows, key=lambda row: abs(row.price_change_pct), reverse=True)


class MovementsCalc:
    """Turn stored price_change_pct rows into honest mover payloads."""

    @staticmethod
    def get_movers(
        filters: MovementsFilters,
        rows: Sequence[MoverReadRow],
    ) -> MoversPage:
        """Movers feed: threshold + direction filters, sort, pagination."""
        threshold = Decimal(str(filters.threshold))
        eligible = [
            row
            for row in rows
            if _matches_threshold(row.price_change_pct, threshold)
            and _matches_direction(row.price_change_pct, filters.direction)
        ]
        ordered = _sort_rows(eligible, filters.sort_by)
        total = len(ordered)
        page_rows = ordered[filters.offset : filters.offset + filters.limit]
        items = [_row_to_mover_item(row) for row in page_rows]
        return MoversPage(
            items=items,
            total=total,
            limit=filters.limit,
            offset=filters.offset,
            has_more=filters.offset + len(items) < total,
        )

    @staticmethod
    def count_movers(
        filters: MovementsFilters,
        rows: Sequence[MoverReadRow],
    ) -> MoversKpi:
        """Count listings whose abs(price_change_pct) exceeds the threshold."""
        threshold = Decimal(str(filters.threshold))
        count = sum(
            1
            for row in rows
            if _matches_threshold(row.price_change_pct, threshold)
        )
        return MoversKpi(count=count)

    @staticmethod
    def movement_summary(
        filters: MovementsFilters,
        rows: Sequence[MoverReadRow],
    ) -> MoversSummary:
        """Up/down/unchanged breakdown, extremes, average abs change, buckets."""
        _ = filters
        up_count = sum(1 for row in rows if row.price_change_pct > 0)
        down_count = sum(1 for row in rows if row.price_change_pct < 0)
        unchanged_count = sum(1 for row in rows if row.price_change_pct == _ZERO)

        items = [_row_to_mover_item(row) for row in rows]
        gainers = [item for item in items if item.price_change_pct > 0]
        losers = [item for item in items if item.price_change_pct < 0]
        biggest_gainer = (
            max(gainers, key=lambda item: item.price_change_pct) if gainers else None
        )
        biggest_loser = (
            min(losers, key=lambda item: item.price_change_pct) if losers else None
        )

        if rows:
            total_abs = sum(abs(row.price_change_pct) for row in rows)
            avg_abs_change = (total_abs / Decimal(len(rows))).quantize(
                Decimal("0.0001"),
                rounding=ROUND_HALF_UP,
            )
        else:
            avg_abs_change = None

        buckets: list[MoversSummaryBucket] = []
        for label, min_pct, max_pct in _SUMMARY_BUCKETS:
            count = 0
            for row in rows:
                magnitude = abs(row.price_change_pct)
                if magnitude < min_pct:
                    continue
                if max_pct is not None and magnitude >= max_pct:
                    continue
                count += 1
            buckets.append(
                MoversSummaryBucket(
                    label=label,
                    min_pct=min_pct,
                    max_pct=max_pct,
                    count=count,
                )
            )

        return MoversSummary(
            up_count=up_count,
            down_count=down_count,
            unchanged_count=unchanged_count,
            biggest_gainer=biggest_gainer,
            biggest_loser=biggest_loser,
            avg_abs_change=avg_abs_change,
            buckets=buckets,
        )

    @staticmethod
    def coverage_meta(
        filters: MovementsFilters,
        counts: MoversCoverageCounts,
    ) -> MoversCoverageMeta:
        """Honest accumulation signal — data_ready only when change history exists."""
        _ = filters
        return MoversCoverageMeta(
            listings_with_change=counts.listings_with_change,
            listings_total=counts.listings_total,
            data_ready=counts.listings_with_change > 0,
        )
