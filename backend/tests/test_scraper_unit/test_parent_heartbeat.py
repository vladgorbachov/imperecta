"""Parent heartbeat pulse during long scrape children."""

from __future__ import annotations

from copy import deepcopy
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.modules.scraper import tasks as scraper_tasks
from app.modules.scraper.fetch_backends import BackendId
from app.modules.scraper.scraper_pool import ListingFetchResult
from app.modules.persist.meta_write import MetaWriteResult
from app.modules.scraper.pipeline import activity_pulse
from app.modules.scraper.pipeline.worker_log_relay import _last_db_pulse


def _make_job_row(*, job_id, metadata=None):
    job = MagicMock()
    job.config = {"metadata": deepcopy(metadata or {})}
    return job


def test_child_pulse_refreshes_parent(monkeypatch):
    child_id = uuid4()
    parent_id = uuid4()
    child_job = _make_job_row(job_id=child_id)
    parent_job = _make_job_row(job_id=parent_id)

    def fake_get(_db, job_id):
        if job_id == child_id:
            return child_job
        if job_id == parent_id:
            return parent_job
        return None

    db = MagicMock()
    db.get.side_effect = fake_get
    db.close = MagicMock()

    monkeypatch.setattr(activity_pulse, "sync_session_factory", lambda: db)
    monkeypatch.setattr(activity_pulse, "push_relay_line", lambda *_a, **_k: None)

    def fake_write_meta_sync(*, fields, **_kwargs):
        from uuid import UUID

        job_id = UUID(str(fields["id"]))
        if job_id == child_id and "config" in fields:
            child_job.config = fields["config"]
        if job_id == parent_id and "config" in fields:
            parent_job.config = fields["config"]
        return MetaWriteResult(ok=True)

    monkeypatch.setattr(activity_pulse, "write_meta_sync", fake_write_meta_sync)
    _last_db_pulse.clear()

    activity_pulse.pulse_job_activity_sync(
        child_id,
        "child line",
        stage="scrape",
        force_db=True,
    )
    activity_pulse.pulse_parent_heartbeat_sync(parent_id, force=True)

    child_meta = child_job.config["metadata"]
    parent_meta = parent_job.config["metadata"]
    assert child_meta.get("last_activity_at") is not None
    assert parent_meta.get("last_activity_at") is not None
    assert child_meta.get("current_stage") == "scrape"
    assert "child line" in (child_meta.get("worker_log_tail") or [])


def test_parent_throttle_key_distinct_from_child(monkeypatch):
    child_id = uuid4()
    parent_id = uuid4()
    pulse_calls: list[tuple] = []

    def track_pulse(job_id, *, force=False):
        pulse_calls.append((job_id, force))
        return False

    monkeypatch.setattr(activity_pulse, "should_pulse_db", track_pulse)
    monkeypatch.setattr(
        activity_pulse,
        "sync_session_factory",
        lambda: (_ for _ in ()).throw(AssertionError("db should not open")),
    )
    monkeypatch.setattr(activity_pulse, "push_relay_line", lambda *_a, **_k: None)
    _last_db_pulse.clear()

    activity_pulse.pulse_job_activity_sync(child_id, "line", force_db=False)
    activity_pulse.pulse_parent_heartbeat_sync(parent_id, force=False)

    assert pulse_calls == [(child_id, False), (parent_id, False)]


def test_parent_heartbeat_failure_does_not_raise(monkeypatch):
    parent_id = uuid4()

    db = MagicMock()
    db.get.side_effect = RuntimeError("db down")
    db.close = MagicMock()
    monkeypatch.setattr(activity_pulse, "sync_session_factory", lambda: db)
    monkeypatch.setattr(activity_pulse, "should_pulse_db", lambda *_a, **_k: True)

    activity_pulse.pulse_parent_heartbeat_sync(parent_id, force=True)


def test_run_scrape_all_pool_threads_parent_heartbeat(monkeypatch):
    child_id = uuid4()
    parent_id = uuid4()
    parent_calls: list[tuple] = []

    def fake_pulse(
        scrape_job_id,
        line,
        *,
        parent_job_id=None,
        force_db=False,
    ):
        parent_calls.append((scrape_job_id, parent_job_id, force_db, line))

    monkeypatch.setattr(scraper_tasks, "_pulse_scrape_activity", fake_pulse)
    monkeypatch.setattr(scraper_tasks, "ScraperPool", MagicMock)
    monkeypatch.setattr(
        scraper_tasks,
        "Settings",
        lambda: MagicMock(scrape_pool_batch_size=10, scrape_pool_max_listings_per_run=10),
    )

    listing_id = uuid4()
    listing = MagicMock(external_url="https://example.test/p/1")
    listing.scraper_config = {}
    listing.marketplace_id = uuid4()

    db = MagicMock()
    batch_result = MagicMock()
    batch_result.all.return_value = [(listing_id,)]
    empty_result = MagicMock()
    empty_result.all.return_value = []

    db.execute.side_effect = [batch_result, empty_result]
    db.get.return_value = listing
    db.close = MagicMock()
    monkeypatch.setattr(scraper_tasks, "sync_session_factory", lambda: db)

    svc = MagicMock()
    svc._listing_scrape_context.return_value = (False, 1, {})
    svc.scrape_listing_from_fetch.return_value = MagicMock(success=True, error=None)
    monkeypatch.setattr(
        scraper_tasks,
        "GlobalScrapeService",
        lambda *_a, **_k: svc,
    )
    monkeypatch.setattr(
        scraper_tasks,
        "_parallel_fetch_listings",
        lambda _pool, specs, deadline_monotonic=None: [
            ListingFetchResult(
                html="<html/>",
                used_backend=BackendId.DIRECT_HTTP,
                last_error="",
                duration_ms=1,
            )
            for _ in specs
        ],
    )

    scraper_tasks._run_scrape_all_pool_impl(
        scrape_job_id=child_id,
        parent_job_id=parent_id,
    )

    assert parent_calls
    assert all(call[1] == parent_id for call in parent_calls)
    assert all(call[0] == child_id for call in parent_calls)
