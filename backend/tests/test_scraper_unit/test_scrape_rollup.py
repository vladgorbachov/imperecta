"""O5a: scrape children aggregation, phase-seed merge, parent-status rule.

Pure unit tests — no DB, no Celery. Mirrors aggregate_discovery_children's test
style for the scrape sibling aggregator; covers merge_phase_seeds and the
decide_parent_status rollup rule.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.modules.scraper.pipeline.child_aggregation import (
    aggregate_scrape_children,
    merge_phase_seeds,
)
from app.modules.scraper.pipeline.job_completion import decide_parent_status


# ---------- aggregate_scrape_children --------------------------------------


@pytest.mark.asyncio
async def test_aggregate_scrape_children_shape_passes_partial_status():
    mp_a = uuid4()
    mp_b = uuid4()
    parent_id = uuid4()

    child_a = MagicMock()
    child_a.marketplace_id = mp_a
    child_a.status = "completed"
    child_a.successful = 7
    child_a.failed = 0
    child_a.duration_ms = 8000
    child_a.config = {"domain": "shop-a.example"}

    child_b = MagicMock()
    child_b.marketplace_id = mp_b
    child_b.status = "partial"
    child_b.successful = 4
    child_b.failed = 2
    child_b.duration_ms = 11000
    child_b.config = {"domain": "shop-b.example"}

    scalars_proxy = MagicMock()
    scalars_proxy.all.return_value = [child_a, child_b]
    select_result = MagicMock()
    select_result.scalars.return_value = scalars_proxy

    db = MagicMock()
    db.execute = AsyncMock(return_value=select_result)

    out = await aggregate_scrape_children(db, parent_id)

    assert set(out.keys()) == {mp_a, mp_b}
    assert out[mp_a] == {
        "marketplace_id": str(mp_a),
        "domain": "shop-a.example",
        "listings_created": 0,
        "prices_saved": 0,
        "errors_count": 0,
        "duration_ms": 8000,
        "status": "completed",
    }
    assert out[mp_b]["status"] == "partial"
    assert out[mp_b]["listings_created"] == 0
    assert out[mp_b]["errors_count"] == 2
    assert out[mp_b]["duration_ms"] == 11000


@pytest.mark.asyncio
async def test_aggregate_scrape_children_handles_nulls():
    parent_id = uuid4()
    mp_id = uuid4()

    child = MagicMock()
    child.marketplace_id = mp_id
    child.status = "failed"
    child.successful = None
    child.failed = None
    child.duration_ms = None
    child.config = None

    scalars_proxy = MagicMock()
    scalars_proxy.all.return_value = [child]
    select_result = MagicMock()
    select_result.scalars.return_value = scalars_proxy

    db = MagicMock()
    db.execute = AsyncMock(return_value=select_result)

    out = await aggregate_scrape_children(db, parent_id)

    assert out[mp_id]["listings_created"] == 0
    assert out[mp_id]["errors_count"] == 0
    assert out[mp_id]["duration_ms"] == 0
    assert out[mp_id]["domain"] is None
    assert out[mp_id]["status"] == "failed"


# ---------- merge_phase_seeds ----------------------------------------------


def _disc_row(mp_id, *, status="completed", listings=10, errs=0, duration_ms=12000):
    return {
        "marketplace_id": str(mp_id),
        "domain": "shop.example",
        "listings_created": listings,
        "prices_saved": 0,
        "errors_count": errs,
        "duration_ms": duration_ms,
        "status": status,
    }


def _scrape_row(mp_id, *, status="completed", errs=0, duration_ms=9000):
    return {
        "marketplace_id": str(mp_id),
        "domain": "shop.example",
        "listings_created": 0,
        "prices_saved": 0,
        "errors_count": errs,
        "duration_ms": duration_ms,
        "status": status,
    }


def test_merge_phase_seeds_discovery_only_marketplace_kept():
    mp = uuid4()
    out = merge_phase_seeds({mp: _disc_row(mp, status="completed")}, {})

    assert set(out.keys()) == {mp}
    assert out[mp]["status"] == "completed"
    assert out[mp]["listings_created"] == 10
    assert out[mp]["errors_count"] == 0


def test_merge_phase_seeds_scrape_only_marketplace_kept():
    mp = uuid4()
    out = merge_phase_seeds({}, {mp: _scrape_row(mp, status="failed", errs=3)})

    assert set(out.keys()) == {mp}
    assert out[mp]["status"] == "failed"
    assert out[mp]["listings_created"] == 0
    assert out[mp]["errors_count"] == 3


def test_merge_phase_seeds_both_present_scrape_status_wins_errors_summed():
    mp = uuid4()
    discovery = {mp: _disc_row(mp, status="completed", listings=20, errs=1, duration_ms=15000)}
    scrape = {mp: _scrape_row(mp, status="partial", errs=4, duration_ms=9000)}

    out = merge_phase_seeds(discovery, scrape)

    assert out[mp]["status"] == "partial"  # scrape terminal wins
    assert out[mp]["errors_count"] == 5    # 1 + 4
    assert out[mp]["listings_created"] == 20  # discovery preserved
    assert out[mp]["duration_ms"] == 15000   # discovery preserved


def test_merge_phase_seeds_disjoint_union():
    mp_a, mp_b = uuid4(), uuid4()
    discovery = {mp_a: _disc_row(mp_a, status="completed")}
    scrape = {mp_b: _scrape_row(mp_b, status="failed", errs=2)}

    out = merge_phase_seeds(discovery, scrape)

    assert set(out.keys()) == {mp_a, mp_b}
    assert out[mp_a]["status"] == "completed"
    assert out[mp_b]["status"] == "failed"
    assert out[mp_b]["errors_count"] == 2


# ---------- decide_parent_status -------------------------------------------


def test_decide_parent_status_hard_error_short_circuits():
    assert decide_parent_status(["completed", "completed"], "broker_unreachable") == "failed"
    assert decide_parent_status([], "broker_unreachable") == "failed"


def test_decide_parent_status_empty_seed_is_failed():
    assert decide_parent_status([], None) == "failed"


def test_decide_parent_status_all_completed():
    assert decide_parent_status(["completed"], None) == "completed"
    assert decide_parent_status(["completed", "completed", "completed"], None) == "completed"


def test_decide_parent_status_all_noncompleted_is_failed():
    assert decide_parent_status(["failed"], None) == "failed"
    assert decide_parent_status(["failed", "partial"], None) == "failed"
    assert decide_parent_status(["partial", "partial"], None) == "failed"


def test_decide_parent_status_mixed_is_partial():
    assert decide_parent_status(["completed", "failed"], None) == "partial"
    assert decide_parent_status(["completed", "partial"], None) == "partial"
    assert decide_parent_status(["completed", "failed", "partial"], None) == "partial"
