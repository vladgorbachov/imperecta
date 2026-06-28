"""Unit tests for the orphan-job reaper.

Covers pure-function liveness decisions and the async impl with mocked
session factory. No real DB, no real Celery."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.workers import reaper_tasks


_NOW = datetime(2026, 6, 7, 12, 0, 0, tzinfo=timezone.utc)
_PIPELINE = "full_pipeline_test"


def test_discovery_below_threshold_not_reaped():
    started = _NOW - timedelta(seconds=100)
    should, age = reaper_tasks._should_reap_job(
        job_type="discovery",
        status="running",
        started_at=started,
        last_activity_at=None,
        pipeline_job_type=_PIPELINE,
        now=_NOW,
    )
    assert should is False
    assert 95 <= age <= 105


def test_discovery_above_threshold_reaped():
    started = _NOW - timedelta(seconds=1300)
    should, age = reaper_tasks._should_reap_job(
        job_type="discovery",
        status="running",
        started_at=started,
        last_activity_at=None,
        pipeline_job_type=_PIPELINE,
        now=_NOW,
    )
    assert should is True
    assert 1295 <= age <= 1305


def test_pipeline_recent_heartbeat_not_reaped():
    last_activity = _NOW - timedelta(seconds=100)
    should, age = reaper_tasks._should_reap_job(
        job_type=_PIPELINE,
        status="running",
        started_at=_NOW - timedelta(seconds=2000),
        last_activity_at=last_activity,
        pipeline_job_type=_PIPELINE,
        now=_NOW,
    )
    assert should is False
    assert 95 <= age <= 105


def test_pipeline_stale_heartbeat_reaped():
    last_activity = _NOW - timedelta(seconds=700)
    should, age = reaper_tasks._should_reap_job(
        job_type=_PIPELINE,
        status="running",
        started_at=_NOW - timedelta(seconds=2000),
        last_activity_at=last_activity,
        pipeline_job_type=_PIPELINE,
        now=_NOW,
    )
    assert should is True
    assert 695 <= age <= 705


def test_pipeline_missing_heartbeat_falls_back_to_started_at():
    started = _NOW - timedelta(seconds=700)
    should, age = reaper_tasks._should_reap_job(
        job_type=_PIPELINE,
        status="running",
        started_at=started,
        last_activity_at=None,
        pipeline_job_type=_PIPELINE,
        now=_NOW,
    )
    assert should is True
    assert 695 <= age <= 705


def test_completed_job_never_reaped():
    should, age = reaper_tasks._should_reap_job(
        job_type="discovery",
        status="completed",
        started_at=_NOW - timedelta(days=7),
        last_activity_at=None,
        pipeline_job_type=_PIPELINE,
        now=_NOW,
    )
    assert should is False
    assert age == 0


def test_unknown_job_type_uses_default_threshold():
    stale_started = _NOW - timedelta(seconds=3700)
    should_stale, age_stale = reaper_tasks._should_reap_job(
        job_type="scheduled",
        status="running",
        started_at=stale_started,
        last_activity_at=None,
        pipeline_job_type=_PIPELINE,
        now=_NOW,
    )
    assert should_stale is True
    assert 3695 <= age_stale <= 3705

    fresh_started = _NOW - timedelta(seconds=100)
    should_fresh, age_fresh = reaper_tasks._should_reap_job(
        job_type="scheduled",
        status="running",
        started_at=fresh_started,
        last_activity_at=None,
        pipeline_job_type=_PIPELINE,
        now=_NOW,
    )
    assert should_fresh is False
    assert 95 <= age_fresh <= 105


class _FakeRow:
    """Mimics a SQLAlchemy Row with attribute access."""

    def __init__(self, *, id, job_type, status, started_at, config):
        self.id = id
        self.job_type = job_type
        self.status = status
        self.started_at = started_at
        self.config = config


def _build_factory_mock(rows: list[_FakeRow], *, child_rows: list[tuple] | None = None):
    """Return (engine, factory, db) wired to yield `rows` from SELECT.

    ``child_rows`` supplies (started_at, config) tuples for the live-child query.
    Defaults to empty (no live children).
    """
    select_calls = {"count": 0}

    select_result = MagicMock()
    select_result.all.return_value = rows

    child_result = MagicMock()
    child_result.all.return_value = child_rows or []

    db = MagicMock()

    async def fake_execute(stmt, params=None):
        if params is not None:
            raise AssertionError("raw SQL UPDATE must not run in reaper")
        select_calls["count"] += 1
        if select_calls["count"] == 1:
            return select_result
        return child_result

    db.execute = AsyncMock(side_effect=fake_execute)
    db.commit = AsyncMock()
    db.rollback = AsyncMock()

    class _SessionCM:
        async def __aenter__(self):
            return db

        async def __aexit__(self, *_a):
            return False

    def factory():
        return _SessionCM()

    engine = MagicMock()
    engine.dispose = AsyncMock()

    return engine, factory, db


@pytest.mark.asyncio
async def test_reap_orphan_jobs_async_marks_stale_rows(monkeypatch):
    now = datetime.now(tz=timezone.utc)
    stale_discovery_id = uuid4()
    fresh_discovery_id = uuid4()
    stale_pipeline_id = uuid4()
    completed_id = uuid4()
    meta_calls: list[dict] = []

    async def fake_meta(**kwargs):
        meta_calls.append(kwargs)
        return MagicMock(ok=True, no_target=False)

    monkeypatch.setattr(reaper_tasks, "write_meta_async", fake_meta)

    rows = [
        _FakeRow(
            id=stale_discovery_id,
            job_type="discovery",
            status="running",
            started_at=now - timedelta(seconds=1300),
            config={},
        ),
        _FakeRow(
            id=fresh_discovery_id,
            job_type="discovery",
            status="running",
            started_at=now - timedelta(seconds=100),
            config={},
        ),
        _FakeRow(
            id=stale_pipeline_id,
            job_type=_PIPELINE,
            status="running",
            started_at=now - timedelta(seconds=2000),
            config={
                "metadata": {
                    "last_activity_at": (
                        now - timedelta(seconds=700)
                    ).isoformat()
                }
            },
        ),
        _FakeRow(
            id=completed_id,
            job_type="discovery",
            status="completed",
            started_at=now - timedelta(seconds=5000),
            config={},
        ),
    ]

    engine, factory, db = _build_factory_mock(rows)
    monkeypatch.setattr(
        reaper_tasks, "_make_session_factory", lambda: (engine, factory)
    )

    result = await reaper_tasks._reap_orphan_jobs_async()

    assert result == {"scanned": 4, "reaped": 2}
    assert len(meta_calls) == 2
    reaped_ids = {call["fields"]["id"] for call in meta_calls}
    assert reaped_ids == {str(stale_discovery_id), str(stale_pipeline_id)}
    assert all(call["fields"]["status"] == "failed" for call in meta_calls)
    db.commit.assert_not_called()
    db.rollback.assert_not_called()
    engine.dispose.assert_awaited_once()


@pytest.mark.asyncio
async def test_parent_has_live_child_fresh_activity():
    now = datetime.now(tz=timezone.utc)
    parent_id = uuid4()
    db = MagicMock()
    child_result = MagicMock()
    child_result.all.return_value = [
        (
            now - timedelta(seconds=100),
            {
                "metadata": {
                    "last_activity_at": (now - timedelta(seconds=100)).isoformat()
                }
            },
        )
    ]
    db.execute = AsyncMock(return_value=child_result)

    live = await reaper_tasks._parent_has_live_child(
        db,
        parent_id,
        now=now,
        stale_seconds=reaper_tasks.REAPER_PIPELINE_HEARTBEAT_STALE_SECONDS,
    )
    assert live is True


@pytest.mark.asyncio
async def test_parent_has_live_child_stale_running_child_not_live():
    """A running child with stale heartbeat must not spare the parent."""
    now = datetime.now(tz=timezone.utc)
    parent_id = uuid4()
    db = MagicMock()
    child_result = MagicMock()
    child_result.all.return_value = [
        (
            now - timedelta(seconds=2000),
            {
                "metadata": {
                    "last_activity_at": (now - timedelta(seconds=900)).isoformat()
                }
            },
        )
    ]
    db.execute = AsyncMock(return_value=child_result)

    live = await reaper_tasks._parent_has_live_child(
        db,
        parent_id,
        now=now,
        stale_seconds=reaper_tasks.REAPER_PIPELINE_HEARTBEAT_STALE_SECONDS,
    )
    assert live is False


@pytest.mark.asyncio
async def test_reaper_spares_parent_with_live_child(monkeypatch):
    now = datetime.now(tz=timezone.utc)
    stale_pipeline_id = uuid4()
    fresh_child_started = now - timedelta(seconds=100)
    fresh_child_config = {
        "metadata": {
            "last_activity_at": (now - timedelta(seconds=100)).isoformat()
        }
    }

    rows = [
        _FakeRow(
            id=stale_pipeline_id,
            job_type=_PIPELINE,
            status="running",
            started_at=now - timedelta(seconds=2000),
            config={
                "metadata": {
                    "last_activity_at": (now - timedelta(seconds=700)).isoformat()
                }
            },
        ),
    ]

    engine, factory, db = _build_factory_mock(
        rows,
        child_rows=[(fresh_child_started, fresh_child_config)],
    )
    monkeypatch.setattr(reaper_tasks, "write_meta_async", AsyncMock())
    monkeypatch.setattr(
        reaper_tasks, "_make_session_factory", lambda: (engine, factory)
    )

    result = await reaper_tasks._reap_orphan_jobs_async()

    assert result == {"scanned": 1, "reaped": 0}
    db.commit.assert_not_called()


@pytest.mark.asyncio
async def test_reaper_reaps_parent_with_no_live_child(monkeypatch):
    now = datetime.now(tz=timezone.utc)
    stale_pipeline_id = uuid4()
    stale_child_started = now - timedelta(seconds=2000)
    stale_child_config = {
        "metadata": {
            "last_activity_at": (now - timedelta(seconds=900)).isoformat()
        }
    }

    meta_calls: list[dict] = []

    async def fake_meta(**kwargs):
        meta_calls.append(kwargs)
        return MagicMock(ok=True, no_target=False)

    monkeypatch.setattr(reaper_tasks, "write_meta_async", fake_meta)

    rows = [
        _FakeRow(
            id=stale_pipeline_id,
            job_type=_PIPELINE,
            status="running",
            started_at=now - timedelta(seconds=2000),
            config={
                "metadata": {
                    "last_activity_at": (now - timedelta(seconds=700)).isoformat()
                }
            },
        ),
    ]

    engine, factory, db = _build_factory_mock(
        rows,
        child_rows=[(stale_child_started, stale_child_config)],
    )
    monkeypatch.setattr(
        reaper_tasks, "_make_session_factory", lambda: (engine, factory)
    )

    result = await reaper_tasks._reap_orphan_jobs_async()

    assert result == {"scanned": 1, "reaped": 1}
    assert meta_calls[0]["fields"]["id"] == str(stale_pipeline_id)


@pytest.mark.asyncio
async def test_reaper_untouched_for_non_pipeline(monkeypatch):
    """Standalone discovery overrun reaping is unchanged by child-awareness."""
    now = datetime.now(tz=timezone.utc)
    stale_discovery_id = uuid4()

    meta_calls: list[dict] = []

    async def fake_meta(**kwargs):
        meta_calls.append(kwargs)
        return MagicMock(ok=True, no_target=False)

    monkeypatch.setattr(reaper_tasks, "write_meta_async", fake_meta)

    rows = [
        _FakeRow(
            id=stale_discovery_id,
            job_type="discovery",
            status="running",
            started_at=now - timedelta(seconds=1300),
            config={},
        ),
    ]

    engine, factory, db = _build_factory_mock(rows)
    monkeypatch.setattr(
        reaper_tasks, "_make_session_factory", lambda: (engine, factory)
    )

    result = await reaper_tasks._reap_orphan_jobs_async()

    assert result == {"scanned": 1, "reaped": 1}
    assert meta_calls[0]["fields"]["id"] == str(stale_discovery_id)


@pytest.mark.asyncio
async def test_reap_orphan_jobs_async_noop_when_nothing_running(monkeypatch):
    monkeypatch.setattr(reaper_tasks, "write_meta_async", AsyncMock())
    engine, factory, db = _build_factory_mock([])
    monkeypatch.setattr(
        reaper_tasks, "_make_session_factory", lambda: (engine, factory)
    )

    result = await reaper_tasks._reap_orphan_jobs_async()

    assert result == {"scanned": 0, "reaped": 0}
    db.commit.assert_not_called()
    engine.dispose.assert_awaited_once()


def test_should_revive_pipeline_tick_window():
    assert reaper_tasks._should_revive_pipeline_tick(120) is False
    assert reaper_tasks._should_revive_pipeline_tick(121) is True
    assert reaper_tasks._should_revive_pipeline_tick(599) is True
    assert reaper_tasks._should_revive_pipeline_tick(600) is False


@pytest.mark.asyncio
async def test_watchdog_revives_stalled_parent(monkeypatch):
    now = datetime.now(tz=timezone.utc)
    parent_id = uuid4()
    rows = [
        _FakeRow(
            id=parent_id,
            job_type=_PIPELINE,
            status="running",
            started_at=now - timedelta(seconds=500),
            config={
                "metadata": {
                    "last_activity_at": (
                        now - timedelta(seconds=200)
                    ).isoformat()
                }
            },
        )
    ]
    engine, factory, _db = _build_factory_mock(rows)
    monkeypatch.setattr(
        reaper_tasks, "_make_session_factory", lambda: (engine, factory)
    )
    apply_async = MagicMock()
    monkeypatch.setattr(
        "app.modules.scraper.tasks.orchestrator_tick.apply_async",
        apply_async,
    )

    result = await reaper_tasks._revive_stalled_pipeline_ticks_async()

    assert result == {"scanned": 1, "revived": 1}
    apply_async.assert_called_once_with([str(parent_id)])
    engine.dispose.assert_awaited_once()


@pytest.mark.asyncio
async def test_watchdog_skips_healthy_and_reaper_owned(monkeypatch):
    now = datetime.now(tz=timezone.utc)
    rows = [
        _FakeRow(
            id=uuid4(),
            job_type=_PIPELINE,
            status="running",
            started_at=now - timedelta(seconds=500),
            config={
                "metadata": {
                    "last_activity_at": (
                        now - timedelta(seconds=60)
                    ).isoformat()
                }
            },
        ),
        _FakeRow(
            id=uuid4(),
            job_type=_PIPELINE,
            status="running",
            started_at=now - timedelta(seconds=2000),
            config={
                "metadata": {
                    "last_activity_at": (
                        now - timedelta(seconds=650)
                    ).isoformat()
                }
            },
        ),
    ]
    engine, factory, _db = _build_factory_mock(rows)
    monkeypatch.setattr(
        reaper_tasks, "_make_session_factory", lambda: (engine, factory)
    )
    apply_async = MagicMock()
    monkeypatch.setattr(
        "app.modules.scraper.tasks.orchestrator_tick.apply_async",
        apply_async,
    )

    result = await reaper_tasks._revive_stalled_pipeline_ticks_async()

    assert result == {"scanned": 2, "revived": 0}
    apply_async.assert_not_called()
