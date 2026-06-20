"""SCRAPE-CHUNKED+COUNTERS: cohort threshold, cooperative deadline, tick resume, log scope."""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.modules.scraper import tasks as scraper_tasks
from app.modules.scraper.pipeline import tick_orchestrator as tick_mod
from app.modules.scraper.pipeline.job_completion import complete_pipeline_job
from app.modules.scraper.pipeline.tick_orchestrator import run_tick


# ---------- 5a cohort threshold --------------------------------------------


def test_scrape_cohort_threshold_used(monkeypatch):
    """stale_before overrides now-6h; None keeps the standalone default."""
    captured: dict = {}

    class _FakeResult:
        def all(self):
            return []

    class _FakeSession:
        def execute(self, stmt):
            captured["stmt"] = stmt
            return _FakeResult()

        def close(self):
            pass

    monkeypatch.setattr(
        scraper_tasks, "sync_session_factory", lambda: _FakeSession()
    )
    monkeypatch.setattr(
        scraper_tasks,
        "GlobalScrapeService",
        lambda *a, **k: MagicMock(),
    )
    monkeypatch.setattr(scraper_tasks, "ScraperPool", lambda: MagicMock())
    monkeypatch.setattr(
        scraper_tasks,
        "Settings",
        lambda: MagicMock(scrape_pool_batch_size=10, scrape_pool_max_listings_per_run=100),
    )

    anchor = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    out = scraper_tasks._run_scrape_all_pool_impl(
        stale_before=anchor,
        deadline_monotonic=time.monotonic() + 3600,
    )
    assert out["deadline_exhausted"] is False
    assert captured.get("stmt") is not None

    with patch.object(scraper_tasks, "datetime") as dt_mock:
        fixed_now = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
        dt_mock.now.return_value = fixed_now
        dt_mock.side_effect = lambda *a, **k: datetime(*a, **k)
        scraper_tasks._run_scrape_all_pool_impl()
        expected_default = fixed_now - timedelta(hours=6)
        # Second call uses default threshold path (no stale_before).
        assert dt_mock.now.called


def test_scrape_deadline_exits_partial(monkeypatch):
    """Past deadline returns deadline_exhausted=True without processing listings."""
    monkeypatch.setattr(
        scraper_tasks,
        "GlobalScrapeService",
        lambda *a, **k: MagicMock(scrape_product=MagicMock()),
    )
    monkeypatch.setattr(scraper_tasks, "ScraperPool", lambda: MagicMock())

    class _FakeResult:
        def all(self):
            return [(uuid4(),)]

    class _FakeSession:
        def execute(self, stmt):
            return _FakeResult()

        def get(self, _lid):
            row = MagicMock()
            row.external_url = "https://example.com/p"
            return row

        def close(self):
            pass

    monkeypatch.setattr(
        scraper_tasks, "sync_session_factory", lambda: _FakeSession()
    )
    monkeypatch.setattr(
        scraper_tasks,
        "Settings",
        lambda: MagicMock(scrape_pool_batch_size=10, scrape_pool_max_listings_per_run=100),
    )

    out = scraper_tasks._run_scrape_all_pool_impl(
        deadline_monotonic=0.0,
    )
    assert out["deadline_exhausted"] is True
    assert out["scraped_ok"] == 0
    assert out["scraped_failed"] == 0


# ---------- 5c scrape child partial on deadline ------------------------------


def _wire_session_factory(monkeypatch, *, get_results):
    engine = MagicMock()
    engine.dispose = AsyncMock()
    db = MagicMock()
    db.get = AsyncMock(side_effect=list(get_results))
    db.commit = AsyncMock()

    class _SessionCM:
        async def __aenter__(self):
            return db

        async def __aexit__(self, *_a):
            return False

    monkeypatch.setattr(
        scraper_tasks, "_make_session_factory", lambda: (engine, lambda: _SessionCM())
    )
    return engine, db


@pytest.mark.asyncio
async def test_scrape_child_partial_on_deadline(monkeypatch):
    child_id = uuid4()
    parent_id = uuid4()
    mp_id = uuid4()

    pending_job = MagicMock()
    pending_job.id = child_id
    pending_job.status = "pending"
    pending_job.marketplace_id = mp_id
    pending_job.parent_job_id = parent_id

    parent_job = MagicMock()
    parent_job.config = {
        "metadata": {"scrape_phase_started_at": "2026-01-01T00:00:00+00:00"}
    }

    marketplace = MagicMock()
    marketplace.id = mp_id
    marketplace.marketplace_code = "shopcode"

    engine, _db = _wire_session_factory(
        monkeypatch, get_results=[pending_job, marketplace, parent_job]
    )

    def fake_run_scrape_all_pool(
        scrape_job_id,
        *,
        marketplace_codes=None,
        stale_before=None,
        deadline_monotonic=None,
        parent_job_id=None,
    ):
        return {
            "scraped_ok": 12,
            "scraped_failed": 0,
            "queued": 12,
            "deadline_exhausted": True,
        }

    monkeypatch.setattr(scraper_tasks, "_run_scrape_all_pool", fake_run_scrape_all_pool)

    out = scraper_tasks.scrape_one_marketplace.run(str(child_id))

    assert out["status"] == "partial"
    assert pending_job.status == "partial"
    assert pending_job.successful == 12
    assert pending_job.failed == 0
    engine.dispose.assert_awaited_once()


# ---------- 5d / 5e tick cohort resume ---------------------------------------


def _mock_db() -> MagicMock:
    db = MagicMock()
    db.execute = AsyncMock()
    db.commit = AsyncMock()
    return db


def _make_job(status: str = "running") -> MagicMock:
    job = MagicMock()
    job.id = uuid4()
    job.status = status
    job.config = {"metadata": {}}
    return job


class _StoreStub:
    def __init__(self, job, metadata: dict):
        self._job = job
        self._metadata = metadata
        self.touch_calls: list[dict] = []

    async def load(self):
        return self._job, self._metadata

    async def touch(self, job, metadata, *, stage=None, extra=None):
        self.touch_calls.append({"stage": stage})
        return metadata


def _install_store(monkeypatch, store: _StoreStub):
    real_store_cls = tick_mod.PipelineMetadataStore

    class _StubFactory:
        marketplace_codes_filter = staticmethod(
            real_store_cls.marketplace_codes_filter
        )

        def __new__(cls, db, job_id):
            return store

    monkeypatch.setattr(tick_mod, "PipelineMetadataStore", _StubFactory)


@pytest.mark.asyncio
async def test_tick_redispatches_mp_with_cohort_remainder(monkeypatch):
    """Terminal child + cohort remainder>0 → MP stays eligible, no phase advance."""
    job = _make_job("running")
    metadata: dict = {
        "phase": "scrape",
        "scrape_marketplace_codes": ["klick"],
        "scrape_phase_started_at": "2026-01-01T00:00:00+00:00",
    }
    store = _StoreStub(job, metadata)
    _install_store(monkeypatch, store)

    for name in (
        "_reap_stale_children",
        "_reconcile_pending_children",
        "_reap_stale_scrape_children",
        "_reconcile_pending_scrape_children",
    ):
        monkeypatch.setattr(tick_mod, name, AsyncMock(return_value=0))
    monkeypatch.setattr(
        tick_mod, "_count_active_scrape_children", AsyncMock(return_value=0)
    )
    monkeypatch.setattr(
        tick_mod,
        "_build_scrape_dispatch_queue",
        AsyncMock(return_value=(["klick"], 0, {"klick": 1})),
    )
    create_mock = AsyncMock(return_value=uuid4())
    monkeypatch.setattr(tick_mod, "_create_pending_scrape_child", create_mock)
    apply_async = MagicMock()
    monkeypatch.setattr(
        "app.modules.scraper.tasks.scrape_one_marketplace.apply_async",
        apply_async,
    )
    reenqueue = MagicMock()
    monkeypatch.setattr(tick_mod, "_reenqueue", reenqueue)

    db = _mock_db()
    locked = MagicMock()
    locked.scalar_one = MagicMock(return_value=True)
    db.execute = AsyncMock(return_value=locked)

    result = await run_tick(db, uuid4())

    assert result["status"] == "ticking"
    assert result["phase"] == "scrape"
    assert metadata["phase"] == "scrape"
    create_mock.assert_awaited_once()
    apply_async.assert_called_once()
    reenqueue.assert_called_once()


@pytest.mark.asyncio
async def test_tick_completes_when_all_cohorts_drained(monkeypatch):
    job = _make_job("running")
    metadata: dict = {
        "phase": "scrape",
        "scrape_marketplace_codes": ["a", "b"],
        "scrape_phase_started_at": "2026-01-01T00:00:00+00:00",
    }
    store = _StoreStub(job, metadata)
    _install_store(monkeypatch, store)

    for name in (
        "_reap_stale_children",
        "_reconcile_pending_children",
        "_reap_stale_scrape_children",
        "_reconcile_pending_scrape_children",
    ):
        monkeypatch.setattr(tick_mod, name, AsyncMock(return_value=0))
    monkeypatch.setattr(
        tick_mod, "_count_active_scrape_children", AsyncMock(return_value=0)
    )
    monkeypatch.setattr(
        tick_mod,
        "_build_scrape_dispatch_queue",
        AsyncMock(return_value=([], 2, {})),
    )
    monkeypatch.setattr(
        tick_mod, "_create_pending_scrape_child", AsyncMock()
    )
    apply_async = MagicMock()
    monkeypatch.setattr(
        "app.modules.scraper.tasks.scrape_one_marketplace.apply_async",
        apply_async,
    )
    reenqueue = MagicMock()
    monkeypatch.setattr(tick_mod, "_reenqueue", reenqueue)

    db = _mock_db()
    locked = MagicMock()
    locked.scalar_one = MagicMock(return_value=True)
    db.execute = AsyncMock(return_value=locked)

    result = await run_tick(db, uuid4())

    assert result == {"status": "phase_advanced", "phase": "complete"}
    assert metadata["phase"] == "complete"
    assert metadata["scrape_marketplace_done"] == 2
    apply_async.assert_not_called()


# ---------- 5f counter scope child ids ---------------------------------------


@pytest.mark.asyncio
async def test_counter_scope_child_ids():
    """ScrapeLog rows under child scrape ids roll up to parent.successful."""
    parent_id = uuid4()
    child_id = uuid4()
    mp_id = uuid4()

    job = MagicMock()
    job.id = parent_id
    job.config = {"metadata": {}}
    job.status = "running"

    child_result = MagicMock()
    child_result.all.return_value = [(child_id,)]

    log_row = MagicMock()
    log_row.marketplace_id = mp_id
    log_row.prices_saved = 3
    log_row.errors_count = 1

    log_result = MagicMock()
    log_result.__iter__ = MagicMock(return_value=iter([log_row]))

    db = MagicMock()
    db.execute = AsyncMock(side_effect=[child_result, log_result])
    db.commit = AsyncMock()

    captured_queries: list = []

    original_execute = db.execute

    async def _capture_execute(stmt):
        captured_queries.append(stmt)
        if len(captured_queries) == 1:
            return child_result
        return log_result

    db.execute = AsyncMock(side_effect=_capture_execute)

    metadata = await complete_pipeline_job(
        db,
        job,
        discovery_ms=0,
        scrape_ms=100,
        persist_ms=0,
        per_marketplace_seed={
            mp_id: {
                "marketplace_id": str(mp_id),
                "domain": "shop.example",
                "listings_created": 5,
                "prices_saved": 0,
                "errors_count": 0,
                "duration_ms": 100,
                "status": "partial",
            }
        },
        hard_error=None,
    )

    assert metadata["summary"]["prices_saved"] == 3
    assert metadata["summary"]["listings_created"] == 5
    assert job.successful == 3
    assert len(captured_queries) == 2
    log_query_sql = str(captured_queries[1])
    assert "scrape_job_id" in log_query_sql.lower()
    assert str(parent_id) not in log_query_sql or "IN" in log_query_sql.upper()
