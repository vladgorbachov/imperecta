"""D5 FAIR-DISPATCH: starvation-free scrape marketplace selection."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.modules.scraper.pipeline import tick_orchestrator as tick_mod
from app.modules.scraper.pipeline.tick_orchestrator import (
    MAX_PARALLEL_SCRAPE,
    TICK_MIN_SECONDS,
    _pick_next_scrape_marketplace,
    run_tick,
)
from tests.test_scraper_unit.test_tick_orchestrator import (
    _StoreStub,
    _install_store,
    _make_job,
    _mock_db,
)


class TestPickNextScrapeMarketplace:
    def test_fair_dispatch_rotates_not_alphabetical(self) -> None:
        """Never-dispatched MPs first; after stamping, undispatched MP is next."""
        eligible = ["barbora", "klick", "rozetka"]
        remainders = {"barbora": 100, "klick": 100, "rozetka": 100}
        last_dispatched: dict[str, str] = {}

        remaining = list(eligible)
        tick1: list[str] = []
        for _ in range(MAX_PARALLEL_SCRAPE):
            code = _pick_next_scrape_marketplace(
                remaining, last_dispatched, remainders
            )
            tick1.append(code)
            remaining.remove(code)
        assert tick1 == ["barbora", "klick"]

        for code in tick1:
            last_dispatched[code] = datetime.now(timezone.utc).isoformat()

        tick2_pick = _pick_next_scrape_marketplace(
            remaining, last_dispatched, remainders
        )
        assert tick2_pick == "rozetka"

    def test_fair_dispatch_partial_reentry_deprioritized(self) -> None:
        """Recent partial big shop loses to never-dispatched smaller shop."""
        eligible = ["barbora", "rozetka"]
        remainders = {"barbora": 500, "rozetka": 50}
        last_dispatched = {
            "barbora": datetime(2026, 6, 20, 12, 0, tzinfo=timezone.utc).isoformat(),
        }
        picked = _pick_next_scrape_marketplace(eligible, last_dispatched, remainders)
        assert picked == "rozetka"

    def test_fair_dispatch_single_mp_unchanged(self) -> None:
        eligible = ["solo"]
        remainders = {"solo": 42}
        assert _pick_next_scrape_marketplace(eligible, {}, remainders) == "solo"
        assert (
            _pick_next_scrape_marketplace(
                eligible,
                {"solo": datetime.now(timezone.utc).isoformat()},
                remainders,
            )
            == "solo"
        )

    def test_fair_dispatch_tiebreak_determinism(self) -> None:
        ts = datetime(2026, 1, 1, tzinfo=timezone.utc).isoformat()
        eligible = ["alpha", "beta"]
        remainders_equal = {"alpha": 10, "beta": 10}
        assert (
            _pick_next_scrape_marketplace(
                eligible, {"alpha": ts, "beta": ts}, remainders_equal
            )
            == "alpha"
        )

        remainders_higher = {"alpha": 5, "beta": 20}
        assert (
            _pick_next_scrape_marketplace(
                eligible, {"alpha": ts, "beta": ts}, remainders_higher
            )
            == "beta"
        )


@pytest.mark.asyncio
async def test_fair_dispatch_completion_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    """All cohorts drained -> phase completes exactly as before."""
    job = _make_job("running")
    metadata: dict = {
        "phase": "scrape",
        "scrape_marketplace_codes": ["a", "b"],
        "scrape_queue": [],
        "scrape_phase_started_at": "2026-01-01T00:00:00+00:00",
        "scrape_last_dispatched_at": {},
    }
    store = _StoreStub(job, metadata)
    _install_store(monkeypatch, store)

    monkeypatch.setattr(tick_mod, "_reap_stale_children", AsyncMock(return_value=0))
    monkeypatch.setattr(tick_mod, "_reconcile_pending_children", AsyncMock(return_value=0))
    monkeypatch.setattr(tick_mod, "_reap_stale_scrape_children", AsyncMock(return_value=0))
    monkeypatch.setattr(
        tick_mod, "_reconcile_pending_scrape_children", AsyncMock(return_value=0)
    )
    monkeypatch.setattr(tick_mod, "_count_active_scrape_children", AsyncMock(return_value=0))
    monkeypatch.setattr(
        tick_mod,
        "_build_scrape_dispatch_queue",
        AsyncMock(return_value=([], 2, {})),
    )
    create_mock = AsyncMock()
    monkeypatch.setattr(tick_mod, "_create_pending_scrape_child", create_mock)
    apply_async = MagicMock()
    monkeypatch.setattr(
        "app.modules.scraper.tasks.scrape_one_marketplace.apply_async",
        apply_async,
    )
    reenqueue = MagicMock()
    monkeypatch.setattr(tick_mod, "_reenqueue", reenqueue)

    result = await run_tick(_mock_db(), uuid4())

    assert result == {"status": "phase_advanced", "phase": "complete"}
    assert metadata["phase"] == "complete"
    create_mock.assert_not_awaited()
    apply_async.assert_not_called()


@pytest.mark.asyncio
async def test_tick_scrape_phase_stamps_last_dispatched(monkeypatch: pytest.MonkeyPatch) -> None:
    """Dispatch stamps scrape_last_dispatched_at for each dispatched MP."""
    parent_id = uuid4()
    job = _make_job("running")
    metadata: dict = {
        "phase": "scrape",
        "scrape_marketplace_codes": ["barbora", "klick", "rozetka"],
        "scrape_queue": ["barbora", "klick", "rozetka"],
        "scrape_total": 3,
        "scrape_phase_started_at": "2026-01-01T00:00:00+00:00",
        "scrape_last_dispatched_at": {},
        "backoff_s": TICK_MIN_SECONDS,
    }
    store = _StoreStub(job, metadata)
    _install_store(monkeypatch, store)

    monkeypatch.setattr(tick_mod, "_reap_stale_children", AsyncMock(return_value=0))
    monkeypatch.setattr(tick_mod, "_reconcile_pending_children", AsyncMock(return_value=0))
    monkeypatch.setattr(tick_mod, "_reap_stale_scrape_children", AsyncMock(return_value=0))
    monkeypatch.setattr(
        tick_mod, "_reconcile_pending_scrape_children", AsyncMock(return_value=0)
    )
    monkeypatch.setattr(tick_mod, "_count_active_scrape_children", AsyncMock(return_value=0))
    remainders = {"barbora": 10, "klick": 10, "rozetka": 10}
    monkeypatch.setattr(
        tick_mod,
        "_build_scrape_dispatch_queue",
        AsyncMock(return_value=(["barbora", "klick", "rozetka"], 0, remainders)),
    )
    created_ids = [uuid4() for _ in range(MAX_PARALLEL_SCRAPE)]
    create_mock = AsyncMock(side_effect=created_ids)
    monkeypatch.setattr(tick_mod, "_create_pending_scrape_child", create_mock)
    apply_async = MagicMock()
    monkeypatch.setattr(
        "app.modules.scraper.tasks.scrape_one_marketplace.apply_async",
        apply_async,
    )
    monkeypatch.setattr(tick_mod, "_reenqueue", MagicMock())

    await run_tick(_mock_db(), parent_id)

    stamped = metadata["scrape_last_dispatched_at"]
    assert set(stamped.keys()) == {"barbora", "klick"}
    assert all(isinstance(v, str) and v for v in stamped.values())
    assert metadata["scrape_queue"] == ["rozetka"]
