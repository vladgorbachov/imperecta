"""O4a: scrape_one_marketplace child task — owner-shell + idempotent skip.

DB, Celery, and the sync scrape bridge are fully mocked; no broker, no real
session, no real scrape. Mirrors test_discover_one_marketplace.py's structure.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.modules.scraper import tasks as scraper_tasks


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
async def test_scrape_one_marketplace_runs_and_owns_job(monkeypatch):
    child_id = uuid4()
    mp_id = uuid4()

    pending_job = MagicMock()
    pending_job.id = child_id
    pending_job.status = "pending"
    pending_job.marketplace_id = mp_id

    marketplace = MagicMock()
    marketplace.id = mp_id
    marketplace.marketplace_code = "shopcode"

    engine, db = _wire_session_factory(
        monkeypatch, get_results=[pending_job, marketplace]
    )

    captured: dict = {}

    def fake_run_scrape_all_pool(scrape_job_id, *, marketplace_codes=None):
        captured["scrape_job_id"] = scrape_job_id
        captured["marketplace_codes"] = marketplace_codes
        return {"scraped_ok": 5, "scraped_failed": 1, "queued": 6}

    monkeypatch.setattr(
        scraper_tasks, "_run_scrape_all_pool", fake_run_scrape_all_pool
    )

    out = scraper_tasks.scrape_one_marketplace.run(str(child_id))

    # O5a: ok=5/failed=1 is a partial outcome (mixed), not "completed".
    assert out["status"] == "partial"
    assert out["child_job_id"] == str(child_id)
    assert out["marketplace_id"] == str(mp_id)
    assert out["scraped_ok"] == 5
    assert out["scraped_failed"] == 1
    assert pending_job.status == "partial"
    assert pending_job.started_at is not None
    assert pending_job.completed_at is not None
    assert pending_job.successful == 5
    assert pending_job.failed == 1
    # scoped to this marketplace's code
    assert captured["marketplace_codes"] == ["shopcode"]
    assert captured["scrape_job_id"] == child_id
    engine.dispose.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "scraped_ok,scraped_failed,error,expected_status",
    [
        (5, 0, None, "completed"),     # ok>0, failed==0 -> completed
        (5, 1, None, "partial"),       # mixed -> partial
        (0, 3, None, "failed"),        # ok==0, failed>0 -> failed
        (5, 1, "broker_dead", "failed"),  # hard_error trumps -> failed
    ],
    ids=["all-ok", "mixed-partial", "all-failed", "hard-error-trumps"],
)
async def test_scrape_one_marketplace_partial_aware_status(
    monkeypatch, scraped_ok, scraped_failed, error, expected_status
):
    """O5a: terminal status is partial-aware (hard_error/ok/failed rule)."""
    child_id = uuid4()
    mp_id = uuid4()

    pending_job = MagicMock()
    pending_job.id = child_id
    pending_job.status = "pending"
    pending_job.marketplace_id = mp_id

    marketplace = MagicMock()
    marketplace.id = mp_id
    marketplace.marketplace_code = "shopcode"

    engine, db = _wire_session_factory(
        monkeypatch, get_results=[pending_job, marketplace]
    )

    def fake_run_scrape_all_pool(scrape_job_id, *, marketplace_codes=None):
        result = {"scraped_ok": scraped_ok, "scraped_failed": scraped_failed}
        if error is not None:
            result["error"] = error
        return result

    monkeypatch.setattr(
        scraper_tasks, "_run_scrape_all_pool", fake_run_scrape_all_pool
    )

    out = scraper_tasks.scrape_one_marketplace.run(str(child_id))

    assert out["status"] == expected_status
    assert pending_job.status == expected_status
    assert pending_job.successful == scraped_ok
    assert pending_job.failed == scraped_failed
    engine.dispose.assert_awaited_once()


@pytest.mark.asyncio
async def test_scrape_one_marketplace_skips_terminal_job(monkeypatch):
    child_id = uuid4()

    finalized_job = MagicMock()
    finalized_job.id = child_id
    finalized_job.status = "completed"

    engine, db = _wire_session_factory(monkeypatch, get_results=[finalized_job])

    scrape_mock = MagicMock()
    monkeypatch.setattr(scraper_tasks, "_run_scrape_all_pool", scrape_mock)

    out = scraper_tasks.scrape_one_marketplace.run(str(child_id))

    assert out == {
        "status": "skipped",
        "job_status": "completed",
        "child_job_id": str(child_id),
    }
    scrape_mock.assert_not_called()
    engine.dispose.assert_awaited_once()


@pytest.mark.asyncio
async def test_scrape_one_marketplace_job_not_found(monkeypatch):
    child_id = uuid4()

    engine, db = _wire_session_factory(monkeypatch, get_results=[None])

    scrape_mock = MagicMock()
    monkeypatch.setattr(scraper_tasks, "_run_scrape_all_pool", scrape_mock)

    out = scraper_tasks.scrape_one_marketplace.run(str(child_id))

    assert out == {"status": "not_found", "child_job_id": str(child_id)}
    scrape_mock.assert_not_called()
    engine.dispose.assert_awaited_once()


@pytest.mark.asyncio
async def test_scrape_one_marketplace_marketplace_not_found(monkeypatch):
    child_id = uuid4()
    mp_id = uuid4()

    pending_job = MagicMock()
    pending_job.id = child_id
    pending_job.status = "pending"
    pending_job.marketplace_id = mp_id

    engine, db = _wire_session_factory(
        monkeypatch, get_results=[pending_job, None]
    )

    scrape_mock = MagicMock()
    monkeypatch.setattr(scraper_tasks, "_run_scrape_all_pool", scrape_mock)

    out = scraper_tasks.scrape_one_marketplace.run(str(child_id))

    assert out["status"] == "marketplace_not_found"
    assert out["child_job_id"] == str(child_id)
    assert pending_job.status == "failed"
    scrape_mock.assert_not_called()
    db.commit.assert_awaited()
    engine.dispose.assert_awaited_once()
