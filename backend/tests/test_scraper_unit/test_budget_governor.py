"""Pure unit tests for discovery budget_governor.allocate."""

from __future__ import annotations

import time

from app.modules.discovery import budget_governor
from app.modules.discovery.budget_governor import PHASE1_BACKLOG_CAP_FRACTION


def test_allocate_none_headroom_returns_none_pair() -> None:
    assert budget_governor.allocate(None, has_backlog=True) == (None, None)
    assert budget_governor.allocate(None, has_backlog=False) == (None, None)


def test_allocate_no_backlog_both_deadlines_equal_headroom() -> None:
    headroom = time.monotonic() + 100.0
    phase1, phase2 = budget_governor.allocate(headroom, has_backlog=False)
    assert phase1 == headroom
    assert phase2 == headroom


def test_allocate_with_backlog_caps_phase1_reserves_phase2_headroom() -> None:
    headroom = time.monotonic() + 100.0
    before = time.monotonic()
    phase1, phase2 = budget_governor.allocate(headroom, has_backlog=True)
    after = time.monotonic()

    assert phase2 == headroom
    remaining = max(0.0, headroom - before)
    expected_cap = before + remaining * PHASE1_BACKLOG_CAP_FRACTION
    assert phase1 is not None
    assert phase1 <= expected_cap + 0.05
    assert phase1 >= before
    assert phase1 < phase2
