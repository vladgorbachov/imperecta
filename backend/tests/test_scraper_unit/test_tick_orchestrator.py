"""O3 unit tests: tick state machine + lifecycle helpers.

No real DB, broker, or Celery worker — every collaborator is mocked. The tests
verify branching of run_tick, dispatch math, re-enqueue scheduling, and the
purity of _next_backoff.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.modules.scraper.pipeline import tick_orchestrator as tick_mod
from app.modules.scraper.pipeline.tick_orchestrator import (
    MAX_PARALLEL_DISCOVERY,
    MAX_PARALLEL_SCRAPE,
    TICK_BACKOFF_FACTOR,
    TICK_MAX_SECONDS,
    TICK_MIN_SECONDS,
    _next_backoff,
    run_tick,
)


# ---------- 6.1 pure backoff -----------------------------------------------


class TestNextBackoff:
    def test_dispatched_resets_to_min(self):
        assert _next_backoff(40.0, dispatched=True) == TICK_MIN_SECONDS
        assert _next_backoff(0.0, dispatched=True) == TICK_MIN_SECONDS

    def test_idle_doubles_until_cap(self):
        assert _next_backoff(5.0, dispatched=False) == 10.0
        assert _next_backoff(20.0, dispatched=False) == 40.0
        assert _next_backoff(40.0, dispatched=False) == TICK_MAX_SECONDS
        assert _next_backoff(TICK_MAX_SECONDS, dispatched=False) == TICK_MAX_SECONDS

    def test_zero_seeds_at_min(self):
        assert _next_backoff(0.0, dispatched=False) == TICK_MIN_SECONDS

    def test_factor_is_two(self):
        assert TICK_BACKOFF_FACTOR == 2.0


# ---------- shared test scaffolding ----------------------------------------


def _make_job(status: str = "running") -> MagicMock:
    job = MagicMock()
    job.id = uuid4()
    job.status = status
    job.config = {"metadata": {}}
    return job


class _StoreStub:
    """Stand-in for PipelineMetadataStore that captures load/touch calls."""

    def __init__(self, job, metadata: dict):
        self._job = job
        self._metadata = metadata
        self.touch_calls: list[dict] = []

    async def load(self):
        return self._job, self._metadata

    async def touch(self, job, metadata, *, stage=None, extra=None):
        self.touch_calls.append(
            {"stage": stage, "metadata_snapshot": dict(metadata)}
        )
        return metadata


def _install_store(monkeypatch, store: _StoreStub):
    """Swap PipelineMetadataStore for a class-like stub that instantiates to
    `store` but still exposes the real `marketplace_codes_filter` staticmethod
    (run_tick reads it during lazy init)."""
    real_store_cls = tick_mod.PipelineMetadataStore

    class _StubFactory:
        marketplace_codes_filter = staticmethod(
            real_store_cls.marketplace_codes_filter
        )

        def __new__(cls, db, job_id):
            return store

    monkeypatch.setattr(tick_mod, "PipelineMetadataStore", _StubFactory)


def _mock_db() -> MagicMock:
    db = MagicMock()
    db.execute = AsyncMock()
    db.commit = AsyncMock()
    db.flush = AsyncMock()
    db.rollback = AsyncMock()
    db.add = MagicMock()
    return db


# ---------- 6.2 lazy init --------------------------------------------------


@pytest.mark.asyncio
async def test_tick_lazy_inits_phase_and_queue(monkeypatch):
    job = _make_job("running")
    metadata: dict = {}
    store = _StoreStub(job, metadata)
    _install_store(monkeypatch, store)

    monkeypatch.setattr(
        tick_mod,
        "_load_active_marketplace_codes",
        AsyncMock(return_value=["a", "b", "c"]),
    )
    monkeypatch.setattr(
        tick_mod, "_reap_stale_children", AsyncMock(return_value=0)
    )
    monkeypatch.setattr(
        tick_mod, "_reconcile_pending_children", AsyncMock(return_value=0)
    )
    monkeypatch.setattr(
        tick_mod, "_count_active_children", AsyncMock(return_value=0)
    )
    monkeypatch.setattr(
        tick_mod, "_create_pending_child", AsyncMock(return_value=uuid4())
    )
    apply_async = MagicMock()
    monkeypatch.setattr(
        "app.modules.scraper.tasks.discover_one_marketplace.apply_async",
        apply_async,
    )
    monkeypatch.setattr(tick_mod, "_reenqueue", MagicMock())

    result = await run_tick(_mock_db(), uuid4())

    assert metadata["phase"] == "discovery"
    assert metadata["mp_total"] == 3
    assert metadata["tick_count"] == 1
    assert metadata["backoff_s"] == TICK_MIN_SECONDS
    assert metadata["resume_attempts"] == 0
    assert result["status"] == "ticking"


# ---------- 6.3 dispatch up to MAX_PARALLEL --------------------------------


@pytest.mark.asyncio
async def test_tick_dispatches_up_to_max_parallel(monkeypatch):
    parent_id = uuid4()
    job = _make_job("running")
    metadata: dict = {
        "phase": "discovery",
        "mp_queue": ["a", "b", "c"],
        "mp_total": 3,
        "backoff_s": TICK_MIN_SECONDS,
    }
    store = _StoreStub(job, metadata)
    _install_store(monkeypatch, store)

    monkeypatch.setattr(
        tick_mod, "_reap_stale_children", AsyncMock(return_value=0)
    )
    monkeypatch.setattr(
        tick_mod, "_reconcile_pending_children", AsyncMock(return_value=0)
    )
    monkeypatch.setattr(
        tick_mod, "_count_active_children", AsyncMock(return_value=0)
    )
    created_ids = [uuid4() for _ in range(2)]
    create_mock = AsyncMock(side_effect=created_ids)
    monkeypatch.setattr(tick_mod, "_create_pending_child", create_mock)
    apply_async = MagicMock()
    monkeypatch.setattr(
        "app.modules.scraper.tasks.discover_one_marketplace.apply_async",
        apply_async,
    )
    reenqueue = MagicMock()
    monkeypatch.setattr(tick_mod, "_reenqueue", reenqueue)

    result = await run_tick(_mock_db(), parent_id)

    assert create_mock.await_count == MAX_PARALLEL_DISCOVERY
    assert apply_async.call_count == MAX_PARALLEL_DISCOVERY
    assert metadata["mp_queue"] == ["c"]
    reenqueue.assert_called_once()
    assert reenqueue.call_args.args[1] == TICK_MIN_SECONDS
    assert result["status"] == "ticking"


# ---------- 6.4 respects existing active children --------------------------


@pytest.mark.asyncio
async def test_tick_respects_existing_active_children(monkeypatch):
    job = _make_job("running")
    metadata: dict = {
        "phase": "discovery",
        "mp_queue": ["a", "b"],
        "mp_total": 4,
        "backoff_s": 5.0,
    }
    store = _StoreStub(job, metadata)
    _install_store(monkeypatch, store)

    monkeypatch.setattr(
        tick_mod, "_reap_stale_children", AsyncMock(return_value=0)
    )
    monkeypatch.setattr(
        tick_mod, "_reconcile_pending_children", AsyncMock(return_value=0)
    )
    monkeypatch.setattr(
        tick_mod,
        "_count_active_children",
        AsyncMock(return_value=MAX_PARALLEL_DISCOVERY),
    )
    create_mock = AsyncMock()
    monkeypatch.setattr(tick_mod, "_create_pending_child", create_mock)
    apply_async = MagicMock()
    monkeypatch.setattr(
        "app.modules.scraper.tasks.discover_one_marketplace.apply_async",
        apply_async,
    )
    reenqueue = MagicMock()
    monkeypatch.setattr(tick_mod, "_reenqueue", reenqueue)

    await run_tick(_mock_db(), uuid4())

    create_mock.assert_not_awaited()
    apply_async.assert_not_called()
    assert metadata["backoff_s"] == 10.0
    reenqueue.assert_called_once()
    assert reenqueue.call_args.args[1] == 10.0


# ---------- 6.5 phase advance to scrape ------------------------------------


@pytest.mark.asyncio
async def test_tick_advances_to_scrape_when_discovery_drained(monkeypatch):
    job = _make_job("running")
    metadata: dict = {
        "phase": "discovery",
        "mp_queue": [],
        "mp_total": 0,
        "backoff_s": 5.0,
    }
    store = _StoreStub(job, metadata)
    _install_store(monkeypatch, store)

    monkeypatch.setattr(
        tick_mod, "_reap_stale_children", AsyncMock(return_value=0)
    )
    monkeypatch.setattr(
        tick_mod, "_reconcile_pending_children", AsyncMock(return_value=0)
    )
    monkeypatch.setattr(
        tick_mod, "_count_active_children", AsyncMock(return_value=0)
    )
    reenqueue = MagicMock()
    monkeypatch.setattr(tick_mod, "_reenqueue", reenqueue)

    result = await run_tick(_mock_db(), uuid4())

    assert result == {"status": "phase_advanced", "phase": "scrape"}
    assert metadata["phase"] == "scrape"
    assert store.touch_calls[-1]["stage"] == "scrape"
    reenqueue.assert_called_once()
    assert reenqueue.call_args.args[1] == TICK_MIN_SECONDS


# ---------- 6.6 scrape phase fan-out (O4b) ---------------------------------


@pytest.mark.asyncio
async def test_tick_scrape_phase_dispatches_children(monkeypatch):
    """Scrape phase mirrors discovery: dispatches up to MAX_PARALLEL_SCRAPE
    scrape_one_marketplace children per tick and shrinks scrape_queue."""
    parent_id = uuid4()
    job = _make_job("running")
    metadata: dict = {
        "phase": "scrape",
        "scrape_queue": ["a", "b", "c"],
        "scrape_total": 3,
        "backoff_s": TICK_MIN_SECONDS,
    }
    store = _StoreStub(job, metadata)
    _install_store(monkeypatch, store)

    # Top-of-tick discovery reap/reconcile is a no-op during scrape phase.
    monkeypatch.setattr(
        tick_mod, "_reap_stale_children", AsyncMock(return_value=0)
    )
    monkeypatch.setattr(
        tick_mod, "_reconcile_pending_children", AsyncMock(return_value=0)
    )
    # Scrape sibling helpers are the active path.
    monkeypatch.setattr(
        tick_mod, "_reap_stale_scrape_children", AsyncMock(return_value=0)
    )
    monkeypatch.setattr(
        tick_mod,
        "_reconcile_pending_scrape_children",
        AsyncMock(return_value=0),
    )
    monkeypatch.setattr(
        tick_mod, "_count_active_scrape_children", AsyncMock(return_value=0)
    )
    created_ids = [uuid4() for _ in range(MAX_PARALLEL_SCRAPE)]
    create_mock = AsyncMock(side_effect=created_ids)
    monkeypatch.setattr(tick_mod, "_create_pending_scrape_child", create_mock)
    apply_async = MagicMock()
    monkeypatch.setattr(
        "app.modules.scraper.tasks.scrape_one_marketplace.apply_async",
        apply_async,
    )
    reenqueue = MagicMock()
    monkeypatch.setattr(tick_mod, "_reenqueue", reenqueue)

    result = await run_tick(_mock_db(), parent_id)

    assert create_mock.await_count == MAX_PARALLEL_SCRAPE
    assert apply_async.call_count == MAX_PARALLEL_SCRAPE
    assert metadata["scrape_queue"] == ["c"]
    assert metadata["scrape_marketplace_total"] == 3
    reenqueue.assert_called_once()
    assert reenqueue.call_args.args[1] == TICK_MIN_SECONDS
    assert result["status"] == "ticking"
    assert result["phase"] == "scrape"


@pytest.mark.asyncio
async def test_tick_scrape_phase_advances_to_complete_when_drained(monkeypatch):
    """Empty scrape queue with no active children flips phase to 'complete'."""
    job = _make_job("running")
    metadata: dict = {
        "phase": "scrape",
        "scrape_queue": [],
        "scrape_total": 0,
    }
    store = _StoreStub(job, metadata)
    _install_store(monkeypatch, store)

    monkeypatch.setattr(
        tick_mod, "_reap_stale_children", AsyncMock(return_value=0)
    )
    monkeypatch.setattr(
        tick_mod, "_reconcile_pending_children", AsyncMock(return_value=0)
    )
    monkeypatch.setattr(
        tick_mod, "_reap_stale_scrape_children", AsyncMock(return_value=0)
    )
    monkeypatch.setattr(
        tick_mod,
        "_reconcile_pending_scrape_children",
        AsyncMock(return_value=0),
    )
    monkeypatch.setattr(
        tick_mod, "_count_active_scrape_children", AsyncMock(return_value=0)
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
    assert store.touch_calls[-1]["stage"] == "persist"
    create_mock.assert_not_awaited()
    apply_async.assert_not_called()
    reenqueue.assert_called_once()
    assert reenqueue.call_args.args[1] == TICK_MIN_SECONDS


@pytest.mark.asyncio
async def test_tick_scrape_phase_first_tick_builds_queue(monkeypatch):
    """On the first scrape tick (no scrape_queue yet) the work list is loaded
    from _load_active_marketplace_codes and immediately dispatched.

    NOTE (O4b contract change): the monolithic scrape phase used to capture a
    hard scrape error into metadata['scrape_error']. Per-child scrape has no
    such concept — failures live on each child's ScrapeJob row + ScrapeLog,
    surfaced by complete_pipeline_job's existing aggregation. No assertion on
    scrape_error here.
    """
    parent_id = uuid4()
    job = _make_job("running")
    metadata: dict = {"phase": "scrape"}  # no scrape_queue
    store = _StoreStub(job, metadata)
    _install_store(monkeypatch, store)

    monkeypatch.setattr(
        tick_mod,
        "_load_active_marketplace_codes",
        AsyncMock(return_value=["a", "b"]),
    )
    monkeypatch.setattr(
        tick_mod, "_reap_stale_children", AsyncMock(return_value=0)
    )
    monkeypatch.setattr(
        tick_mod, "_reconcile_pending_children", AsyncMock(return_value=0)
    )
    monkeypatch.setattr(
        tick_mod, "_reap_stale_scrape_children", AsyncMock(return_value=0)
    )
    monkeypatch.setattr(
        tick_mod,
        "_reconcile_pending_scrape_children",
        AsyncMock(return_value=0),
    )
    monkeypatch.setattr(
        tick_mod, "_count_active_scrape_children", AsyncMock(return_value=0)
    )
    created_ids = [uuid4() for _ in range(2)]
    create_mock = AsyncMock(side_effect=created_ids)
    monkeypatch.setattr(tick_mod, "_create_pending_scrape_child", create_mock)
    apply_async = MagicMock()
    monkeypatch.setattr(
        "app.modules.scraper.tasks.scrape_one_marketplace.apply_async",
        apply_async,
    )
    monkeypatch.setattr(tick_mod, "_reenqueue", MagicMock())

    await run_tick(_mock_db(), parent_id)

    assert metadata["scrape_total"] == 2
    assert apply_async.call_count == MAX_PARALLEL_SCRAPE  # 2 dispatched
    assert "scrape_error" not in metadata


# ---------- 6.7 complete phase finalizes + stops ---------------------------


@pytest.mark.asyncio
async def test_tick_complete_phase_finalizes_and_stops(monkeypatch):
    parent_id = uuid4()
    job = _make_job("running")
    metadata: dict = {"phase": "complete"}
    store = _StoreStub(job, metadata)
    _install_store(monkeypatch, store)

    monkeypatch.setattr(
        tick_mod, "_reap_stale_children", AsyncMock(return_value=0)
    )
    monkeypatch.setattr(
        tick_mod, "_reconcile_pending_children", AsyncMock(return_value=0)
    )

    per_mp = {uuid4(): {"marketplace_id": "x", "status": "completed"}}
    aggregator = AsyncMock(return_value=per_mp)
    monkeypatch.setattr(
        "app.modules.scraper.pipeline.child_aggregation.aggregate_discovery_children",
        aggregator,
    )
    # O5a: tick now also calls aggregate_scrape_children + merge_phase_seeds.
    # Empty scrape seed -> merge yields the discovery seed by value.
    scrape_aggregator = AsyncMock(return_value={})
    monkeypatch.setattr(
        "app.modules.scraper.pipeline.child_aggregation.aggregate_scrape_children",
        scrape_aggregator,
    )
    completer = AsyncMock(return_value={})
    monkeypatch.setattr(
        "app.modules.scraper.pipeline.job_completion.complete_pipeline_job",
        completer,
    )
    reenqueue = MagicMock()
    monkeypatch.setattr(tick_mod, "_reenqueue", reenqueue)

    result = await run_tick(_mock_db(), parent_id)

    completer.assert_awaited_once()
    kwargs = completer.await_args.kwargs
    # Loosened from `is` to `==` because merge_phase_seeds returns a new dict.
    assert kwargs["per_marketplace_seed"] == per_mp
    reenqueue.assert_not_called()
    assert result["status"] == "complete"


# ---------- 6.8 parent not running stops the loop --------------------------


@pytest.mark.asyncio
async def test_tick_stops_when_parent_not_running(monkeypatch):
    job = _make_job("cancelled")
    metadata: dict = {"phase": "discovery", "mp_queue": ["a"], "mp_total": 1}
    store = _StoreStub(job, metadata)
    _install_store(monkeypatch, store)

    create_mock = AsyncMock()
    monkeypatch.setattr(tick_mod, "_create_pending_child", create_mock)
    apply_async = MagicMock()
    monkeypatch.setattr(
        "app.modules.scraper.tasks.discover_one_marketplace.apply_async",
        apply_async,
    )
    reenqueue = MagicMock()
    monkeypatch.setattr(tick_mod, "_reenqueue", reenqueue)

    result = await run_tick(_mock_db(), uuid4())

    assert result == {"status": "stopped", "job_status": "cancelled"}
    create_mock.assert_not_awaited()
    apply_async.assert_not_called()
    reenqueue.assert_not_called()


@pytest.mark.asyncio
async def test_tick_not_found_stops(monkeypatch):
    store = _StoreStub(None, {})
    _install_store(monkeypatch, store)
    reenqueue = MagicMock()
    monkeypatch.setattr(tick_mod, "_reenqueue", reenqueue)

    result = await run_tick(_mock_db(), uuid4())

    assert result == {"status": "not_found"}
    reenqueue.assert_not_called()


@pytest.mark.asyncio
async def test_tick_unknown_phase_stops(monkeypatch):
    job = _make_job("running")
    metadata: dict = {"phase": "garbage"}
    store = _StoreStub(job, metadata)
    _install_store(monkeypatch, store)
    monkeypatch.setattr(
        tick_mod, "_reap_stale_children", AsyncMock(return_value=0)
    )
    monkeypatch.setattr(
        tick_mod, "_reconcile_pending_children", AsyncMock(return_value=0)
    )
    reenqueue = MagicMock()
    monkeypatch.setattr(tick_mod, "_reenqueue", reenqueue)

    result = await run_tick(_mock_db(), uuid4())

    assert result == {"status": "unknown_phase", "phase": "garbage"}
    reenqueue.assert_not_called()


# ---------- 6.9 reap / reconcile helpers -----------------------------------


@pytest.mark.asyncio
async def test_reap_stale_children_issues_update(monkeypatch):
    parent_id = uuid4()
    reaped_id = uuid4()
    db = _mock_db()
    exec_result = MagicMock()
    exec_result.all.return_value = [(reaped_id,)]
    db.execute = AsyncMock(return_value=exec_result)

    n = await tick_mod._reap_stale_children(db, parent_id)

    assert n == 1
    db.execute.assert_awaited_once()
    sql_arg = db.execute.await_args.args[0]
    # bound TextClause — stringify and look for the UPDATE we expect
    rendered = str(sql_arg).lower()
    assert "update scrape_jobs" in rendered
    assert "status = 'failed'" in rendered
    db.commit.assert_awaited()


@pytest.mark.asyncio
async def test_reap_stale_children_zero_skips_commit(monkeypatch):
    db = _mock_db()
    exec_result = MagicMock()
    exec_result.all.return_value = []
    db.execute = AsyncMock(return_value=exec_result)

    n = await tick_mod._reap_stale_children(db, uuid4())

    assert n == 0
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_reconcile_pending_redispatches(monkeypatch):
    parent_id = uuid4()
    pending_ids = [uuid4(), uuid4()]
    db = _mock_db()
    exec_result = MagicMock()
    exec_result.all.return_value = [(pid,) for pid in pending_ids]
    db.execute = AsyncMock(return_value=exec_result)
    apply_async = MagicMock()
    monkeypatch.setattr(
        "app.modules.scraper.tasks.discover_one_marketplace.apply_async",
        apply_async,
    )

    n = await tick_mod._reconcile_pending_children(db, parent_id)

    assert n == 2
    assert apply_async.call_count == 2
    dispatched_args = [c.args[0][0] for c in apply_async.call_args_list]
    assert set(dispatched_args) == {str(pid) for pid in pending_ids}


@pytest.mark.asyncio
async def test_reconcile_pending_empty_returns_zero(monkeypatch):
    db = _mock_db()
    exec_result = MagicMock()
    exec_result.all.return_value = []
    db.execute = AsyncMock(return_value=exec_result)
    apply_async = MagicMock()
    monkeypatch.setattr(
        "app.modules.scraper.tasks.discover_one_marketplace.apply_async",
        apply_async,
    )

    n = await tick_mod._reconcile_pending_children(db, uuid4())

    assert n == 0
    apply_async.assert_not_called()


# ---------- 6.10 create_pending_child unknown code -------------------------


@pytest.mark.asyncio
async def test_create_pending_child_returns_none_for_unknown_code():
    db = _mock_db()
    exec_result = MagicMock()
    exec_result.scalar_one_or_none = MagicMock(return_value=None)
    db.execute = AsyncMock(return_value=exec_result)

    out = await tick_mod._create_pending_child(db, uuid4(), "nope")

    assert out is None
    db.add.assert_not_called()
    db.flush.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_pending_child_inserts_and_returns_id():
    parent_id = uuid4()
    mp = MagicMock()
    mp.id = uuid4()
    mp.domain = "shop.example"
    db = _mock_db()
    exec_result = MagicMock()
    exec_result.scalar_one_or_none = MagicMock(return_value=mp)
    db.execute = AsyncMock(return_value=exec_result)

    # ScrapeJob.id is populated by SQLAlchemy during a real flush (via
    # ``default=uuid.uuid4`` on the column). The mocked flush would otherwise
    # leave it None and the helper would return None — simulate the real
    # behavior by assigning a fresh UUID inside flush's side_effect.
    async def _flush_side_effect():
        if db.add.call_args is not None:
            added = db.add.call_args.args[0]
            if added.id is None:
                added.id = uuid4()

    db.flush = AsyncMock(side_effect=_flush_side_effect)

    out = await tick_mod._create_pending_child(db, parent_id, "shop")

    assert isinstance(out, type(uuid4()))
    db.add.assert_called_once()
    added_job = db.add.call_args.args[0]
    assert added_job.parent_job_id == parent_id
    assert added_job.marketplace_id == mp.id
    assert added_job.status == "pending"
    assert added_job.config == {"domain": "shop.example"}
    assert added_job.id == out
    db.flush.assert_awaited_once()


# ---------- _reenqueue uses apply_async with countdown ---------------------


def test_reenqueue_uses_apply_async_with_countdown(monkeypatch):
    apply_async = MagicMock()
    monkeypatch.setattr(
        "app.modules.scraper.tasks.orchestrator_tick.apply_async", apply_async
    )

    parent_id = uuid4()
    tick_mod._reenqueue(parent_id, 7.5)

    apply_async.assert_called_once()
    args, kwargs = apply_async.call_args
    assert args[0] == [str(parent_id)]
    assert kwargs.get("countdown") == 7.5
