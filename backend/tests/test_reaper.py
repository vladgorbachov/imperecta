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


def _build_factory_mock(rows: list[_FakeRow]):
    """Return (engine, factory, db, update_calls) wired to yield `rows`."""
    update_calls: list[dict] = []

    select_result = MagicMock()
    select_result.all.return_value = rows

    db = MagicMock()

    async def fake_execute(stmt, params=None):
        if params is not None:
            update_calls.append(dict(params))
            return MagicMock()
        return select_result

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

    return engine, factory, db, update_calls


@pytest.mark.asyncio
async def test_reap_orphan_jobs_async_marks_stale_rows(monkeypatch):
    now = datetime.now(tz=timezone.utc)
    stale_discovery_id = uuid4()
    fresh_discovery_id = uuid4()
    stale_pipeline_id = uuid4()
    completed_id = uuid4()

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

    engine, factory, db, update_calls = _build_factory_mock(rows)
    monkeypatch.setattr(
        reaper_tasks, "_make_session_factory", lambda: (engine, factory)
    )

    result = await reaper_tasks._reap_orphan_jobs_async()

    assert result == {"scanned": 4, "reaped": 2}
    assert len(update_calls) == 1
    assert set(update_calls[0]["ids"]) == {stale_discovery_id, stale_pipeline_id}
    db.commit.assert_awaited_once()
    db.rollback.assert_not_called()
    engine.dispose.assert_awaited_once()


@pytest.mark.asyncio
async def test_reap_orphan_jobs_async_noop_when_nothing_running(monkeypatch):
    engine, factory, db, update_calls = _build_factory_mock([])
    monkeypatch.setattr(
        reaper_tasks, "_make_session_factory", lambda: (engine, factory)
    )

    result = await reaper_tasks._reap_orphan_jobs_async()

    assert result == {"scanned": 0, "reaped": 0}
    assert update_calls == []
    db.commit.assert_not_called()
    engine.dispose.assert_awaited_once()
