"""O2: discover_one_marketplace child task and aggregate_discovery_children.

DB and Celery are fully mocked; no broker, no real session."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.modules.scraper import tasks as scraper_tasks
from app.modules.scraper.pipeline.child_aggregation import (
    aggregate_discovery_children,
)


def _wire_session_factory(monkeypatch, *, get_results):
    """Patch _make_session_factory to yield a mock engine + factory.

    `get_results` is an iterable of objects returned by successive db.get
    calls. Returns (engine, db) so tests can introspect them.
    """
    engine = MagicMock()
    engine.dispose = AsyncMock()

    db = MagicMock()
    db.get = AsyncMock(side_effect=list(get_results))
    db.commit = AsyncMock()
    db.rollback = AsyncMock()

    class _SessionCM:
        async def __aenter__(self):
            return db

        async def __aexit__(self, *_a):
            return False

    def factory():
        return _SessionCM()

    monkeypatch.setattr(
        scraper_tasks, "_make_session_factory", lambda: (engine, factory)
    )
    return engine, db


@pytest.mark.asyncio
async def test_discover_one_marketplace_runs_and_owns_job(monkeypatch):
    from app.modules.scraper.discovery import DiscoveryResult

    child_id = uuid4()
    mp_id = uuid4()

    pending_job = MagicMock()
    pending_job.id = child_id
    pending_job.status = "pending"
    pending_job.marketplace_id = mp_id

    marketplace = MagicMock()
    marketplace.id = mp_id

    engine, db = _wire_session_factory(
        monkeypatch, get_results=[pending_job, marketplace]
    )

    async def fake_discover(self, mp, **kwargs):
        assert kwargs.get("inner_job") is pending_job
        assert "deadline_monotonic" in kwargs and kwargs["deadline_monotonic"] is not None
        return DiscoveryResult(
            marketplace_id=mp.id,
            status="completed",
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            persisted_listings=7,
        )

    monkeypatch.setattr(
        "app.modules.scraper.discovery.DiscoveryCrawler.discover",
        fake_discover,
    )

    out = scraper_tasks.discover_one_marketplace.run(str(child_id))

    assert out["status"] == "completed"
    assert out["child_job_id"] == str(child_id)
    assert out["marketplace_id"] == str(mp_id)
    assert out["products_new"] == 7
    engine.dispose.assert_awaited_once()


@pytest.mark.asyncio
async def test_discover_one_marketplace_skips_terminal_job(monkeypatch):
    child_id = uuid4()

    finalized_job = MagicMock()
    finalized_job.id = child_id
    finalized_job.status = "completed"

    engine, db = _wire_session_factory(monkeypatch, get_results=[finalized_job])

    discover_mock = AsyncMock()
    monkeypatch.setattr(
        "app.modules.scraper.discovery.DiscoveryCrawler.discover",
        discover_mock,
    )

    out = scraper_tasks.discover_one_marketplace.run(str(child_id))

    assert out == {
        "status": "skipped",
        "job_status": "completed",
        "child_job_id": str(child_id),
    }
    discover_mock.assert_not_awaited()
    engine.dispose.assert_awaited_once()


@pytest.mark.asyncio
async def test_discover_one_marketplace_job_not_found(monkeypatch):
    child_id = uuid4()

    engine, db = _wire_session_factory(monkeypatch, get_results=[None])

    discover_mock = AsyncMock()
    monkeypatch.setattr(
        "app.modules.scraper.discovery.DiscoveryCrawler.discover",
        discover_mock,
    )

    out = scraper_tasks.discover_one_marketplace.run(str(child_id))

    assert out == {"status": "not_found", "child_job_id": str(child_id)}
    discover_mock.assert_not_awaited()
    engine.dispose.assert_awaited_once()


@pytest.mark.asyncio
async def test_discover_one_marketplace_marketplace_not_found(monkeypatch):
    child_id = uuid4()
    mp_id = uuid4()

    pending_job = MagicMock()
    pending_job.id = child_id
    pending_job.status = "pending"
    pending_job.marketplace_id = mp_id

    engine, db = _wire_session_factory(
        monkeypatch, get_results=[pending_job, None]
    )

    discover_mock = AsyncMock()
    monkeypatch.setattr(
        "app.modules.scraper.discovery.DiscoveryCrawler.discover",
        discover_mock,
    )

    out = scraper_tasks.discover_one_marketplace.run(str(child_id))

    assert out["status"] == "marketplace_not_found"
    assert out["child_job_id"] == str(child_id)
    assert pending_job.status == "failed"
    discover_mock.assert_not_awaited()
    db.commit.assert_awaited()
    engine.dispose.assert_awaited_once()


@pytest.mark.asyncio
async def test_aggregate_discovery_children_shape():
    mp_a = uuid4()
    mp_b = uuid4()
    parent_id = uuid4()

    child_a = MagicMock()
    child_a.marketplace_id = mp_a
    child_a.status = "completed"
    child_a.successful = 10
    child_a.failed = 0
    child_a.duration_ms = 12000
    child_a.config = {"domain": "shop-a.example"}

    child_b = MagicMock()
    child_b.marketplace_id = mp_b
    child_b.status = "partial"
    child_b.successful = 3
    child_b.failed = 1
    child_b.duration_ms = 9000
    child_b.config = {"domain": "shop-b.example"}

    scalars_proxy = MagicMock()
    scalars_proxy.all.return_value = [child_a, child_b]
    select_result = MagicMock()
    select_result.scalars.return_value = scalars_proxy

    db = MagicMock()
    db.execute = AsyncMock(return_value=select_result)

    out = await aggregate_discovery_children(db, parent_id)

    assert set(out.keys()) == {mp_a, mp_b}
    assert out[mp_a] == {
        "marketplace_id": str(mp_a),
        "domain": "shop-a.example",
        "listings_created": 10,
        "prices_saved": 0,
        "errors_count": 0,
        "duration_ms": 12000,
        "status": "completed",
    }
    assert out[mp_b]["status"] == "partial"
    assert out[mp_b]["listings_created"] == 3
    assert out[mp_b]["errors_count"] == 1


@pytest.mark.asyncio
async def test_aggregate_discovery_children_handles_nulls():
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

    out = await aggregate_discovery_children(db, parent_id)

    assert out[mp_id]["listings_created"] == 0
    assert out[mp_id]["errors_count"] == 0
    assert out[mp_id]["duration_ms"] == 0
    assert out[mp_id]["domain"] is None
    assert out[mp_id]["status"] == "failed"
