"""DB-free MovementsCalc tests over stub read rows."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from app.modules.visualisation_calc.movements.read import MoverReadRow, MoversCoverageCounts
from app.modules.visualisation_calc.movements.schemas import MovementsFilters
from app.modules.visualisation_calc.movements.service import MovementsCalc


def _row(
    *,
    pct: Decimal | None,
    changed_at: datetime | None = None,
    prior: Decimal | None = Decimal("100.00"),
    new_price: Decimal = Decimal("120.00"),
    country: str = "DE",
    marketplace_id=None,
    category_id=None,
    marketplace_domain: str | None = "example.de",
) -> MoverReadRow:
    if pct is None:
        raise ValueError("use _null_pct_row for NULL pct fixtures")
    return MoverReadRow(
        listing_id=uuid4(),
        product_name="Widget",
        image_url="https://example.com/img.jpg",
        marketplace_id=marketplace_id or uuid4(),
        marketplace_name="Example Shop",
        marketplace_domain=marketplace_domain,
        country_code=country,
        country_name="Germany",
        category_id=category_id,
        category_name="Gadgets",
        new_price=new_price,
        currency_code="EUR",
        price_change_pct=pct,
        changed_at=changed_at or datetime(2026, 6, 17, 12, 0, tzinfo=UTC),
        prior_fact_price=prior,
    )


def test_get_movers_default_threshold_and_sort() -> None:
    rows = [
        _row(pct=Decimal("6.0")),
        _row(pct=Decimal("-12.0")),
        _row(pct=Decimal("3.0")),
    ]
    filters = MovementsFilters(threshold=Decimal("5.0"))
    page = MovementsCalc.get_movers(filters, rows)

    assert page.total == 2
    assert len(page.items) == 2
    assert page.items[0].price_change_pct == Decimal("-12.0")
    assert page.items[1].price_change_pct == Decimal("6.0")
    assert page.has_more is False


def test_get_movers_direction_up_filter() -> None:
    rows = [_row(pct=Decimal("8.0")), _row(pct=Decimal("-9.0"))]
    page = MovementsCalc.get_movers(
        MovementsFilters(direction="up", threshold=Decimal("5.0")),
        rows,
    )
    assert page.total == 1
    assert page.items[0].direction == "up"


def test_get_movers_pagination() -> None:
    rows = [_row(pct=Decimal("10.0")), _row(pct=Decimal("20.0")), _row(pct=Decimal("30.0"))]
    page = MovementsCalc.get_movers(
        MovementsFilters(limit=2, offset=1, threshold=Decimal("5.0")),
        rows,
    )
    assert page.total == 3
    assert len(page.items) == 2
    assert page.has_more is False
    assert page.items[0].price_change_pct == Decimal("20.0")


def test_count_movers_respects_threshold() -> None:
    rows = [
        _row(pct=Decimal("6.0")),
        _row(pct=Decimal("4.9")),
        _row(pct=Decimal("-7.0")),
    ]
    kpi = MovementsCalc.count_movers(MovementsFilters(threshold=Decimal("5.0")), rows)
    assert kpi.count == 2


def test_null_pct_rows_never_emitted_by_read_contract() -> None:
    """Read excludes NULL; service never sees NULL in mover feed."""
    rows = [_row(pct=Decimal("0.00"))]
    page = MovementsCalc.get_movers(MovementsFilters(threshold=Decimal("0.01")), rows)
    assert page.total == 0


def test_unchanged_zero_counted_in_summary_not_as_mover() -> None:
    rows = [_row(pct=Decimal("0.00"), prior=Decimal("50.00"), new_price=Decimal("50.00"))]
    summary = MovementsCalc.movement_summary(MovementsFilters(), rows)
    movers = MovementsCalc.get_movers(MovementsFilters(threshold=Decimal("5.0")), rows)

    assert summary.unchanged_count == 1
    assert summary.up_count == 0
    assert summary.down_count == 0
    assert movers.total == 0


def test_movement_summary_biggest_gainer_and_loser() -> None:
    rows = [
        _row(pct=Decimal("15.0"), prior=Decimal("100"), new_price=Decimal("115")),
        _row(pct=Decimal("-8.0"), prior=Decimal("200"), new_price=Decimal("184")),
        _row(pct=Decimal("3.0"), prior=Decimal("50"), new_price=Decimal("51.5")),
    ]
    summary = MovementsCalc.movement_summary(MovementsFilters(), rows)

    assert summary.biggest_gainer is not None
    assert summary.biggest_gainer.price_change_pct == Decimal("15.0")
    assert summary.biggest_loser is not None
    assert summary.biggest_loser.price_change_pct == Decimal("-8.0")
    assert summary.avg_abs_change == Decimal("8.6667")


def test_movement_summary_buckets() -> None:
    rows = [
        _row(pct=Decimal("3.0")),
        _row(pct=Decimal("7.0")),
        _row(pct=Decimal("15.0")),
        _row(pct=Decimal("25.0")),
    ]
    summary = MovementsCalc.movement_summary(MovementsFilters(), rows)
    counts = {bucket.label: bucket.count for bucket in summary.buckets}
    assert counts["0–5%"] == 1
    assert counts["5–10%"] == 1
    assert counts["10–20%"] == 1
    assert counts["20%+"] == 1


def test_old_price_uses_prior_fact_price_when_present() -> None:
    row = _row(
        pct=Decimal("20.0"),
        prior=Decimal("100.00"),
        new_price=Decimal("120.00"),
    )
    item = MovementsCalc.get_movers(MovementsFilters(threshold=Decimal("5.0")), [row]).items[0]
    assert item.old_price == Decimal("100.00")
    assert item.old_price_reconstructed is False


def test_old_price_reconstructed_when_no_prior_row() -> None:
    row = _row(
        pct=Decimal("20.0"),
        prior=None,
        new_price=Decimal("120.00"),
    )
    item = MovementsCalc.get_movers(MovementsFilters(threshold=Decimal("5.0")), [row]).items[0]
    assert item.old_price == Decimal("100.00")
    assert item.old_price_reconstructed is True


def test_coverage_meta_empty_db() -> None:
    meta = MovementsCalc.coverage_meta(
        MovementsFilters(),
        MoversCoverageCounts(listings_total=10, listings_with_change=0),
    )
    assert meta.data_ready is False
    assert meta.listings_total == 10
    assert meta.listings_with_change == 0


def test_coverage_meta_ready_when_history_exists() -> None:
    meta = MovementsCalc.coverage_meta(
        MovementsFilters(),
        MoversCoverageCounts(listings_total=5, listings_with_change=2),
    )
    assert meta.data_ready is True


def test_empty_feed_returns_zero_counts() -> None:
    page = MovementsCalc.get_movers(MovementsFilters(), [])
    kpi = MovementsCalc.count_movers(MovementsFilters(), [])
    summary = MovementsCalc.movement_summary(MovementsFilters(), [])

    assert page.total == 0
    assert page.items == []
    assert kpi.count == 0
    assert summary.avg_abs_change is None
    assert summary.biggest_gainer is None
    assert summary.biggest_loser is None


def test_decimal_direction_up_down() -> None:
    up = MovementsCalc.get_movers(
        MovementsFilters(threshold=Decimal("1.0")),
        [_row(pct=Decimal("2.5000"))],
    ).items[0]
    down = MovementsCalc.get_movers(
        MovementsFilters(threshold=Decimal("1.0")),
        [_row(pct=Decimal("-2.5000"))],
    ).items[0]
    assert up.direction == "up"
    assert down.direction == "down"
