"""OBSERVABILITY-FIX: child tasks open the relay CM under PARENT id and wire
``on_activity`` into DiscoveryCrawler; discovery emits at Phase 0 / Phase 1
stage-points.

The relay CM is mocked at the module-symbol seen by ``tasks.py`` so the test
asserts the wiring without touching Redis. ``on_activity`` capture confirms
the discovery callback is bound to the parent_id (not the child_id).
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from app.modules.scraper import discovery as disc
from app.modules.scraper import tasks as scraper_tasks


@contextmanager
def _record_cm(captured: list):
    @contextmanager
    def _cm(job_id):
        captured.append(job_id)
        yield

    yield _cm


def _wire_session_factory(monkeypatch, *, get_results):
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

    monkeypatch.setattr(
        scraper_tasks,
        "_make_session_factory",
        lambda: (engine, lambda: _SessionCM()),
    )
    return engine, db


@pytest.mark.asyncio
async def test_discover_one_marketplace_opens_cm_under_parent_id(monkeypatch):
    """The discover child must open ``pipeline_worker_log_relay(parent_id)``
    where parent_id == ``job.parent_job_id`` (NOT the child_job_id), so the
    admin live monitor — which polls the parent — sees the lines.
    """
    from app.modules.scraper.discovery import DiscoveryResult

    child_id = uuid4()
    parent_id = uuid4()
    mp_id = uuid4()

    pending_job = MagicMock()
    pending_job.id = child_id
    pending_job.status = "pending"
    pending_job.marketplace_id = mp_id
    pending_job.parent_job_id = parent_id

    marketplace = MagicMock()
    marketplace.id = mp_id

    _wire_session_factory(
        monkeypatch, get_results=[pending_job, marketplace]
    )

    cm_calls: list[UUID] = []

    @contextmanager
    def fake_cm(job_id: UUID):
        cm_calls.append(job_id)
        yield

    monkeypatch.setattr(scraper_tasks, "pipeline_worker_log_relay", fake_cm)

    captured_on_activity: list = []

    async def fake_discover(self, mp, **kwargs):
        # Capture on_activity to verify it's wired to the parent.
        if self._on_activity is not None:
            captured_on_activity.append(self._on_activity)
        return DiscoveryResult(
            marketplace_id=mp.id,
            status="completed",
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            persisted_listings=3,
        )

    monkeypatch.setattr(
        "app.modules.scraper.discovery.DiscoveryCrawler.discover",
        fake_discover,
    )

    out = scraper_tasks.discover_one_marketplace.run(str(child_id))

    assert out["status"] == "completed"
    assert cm_calls == [parent_id]
    assert len(captured_on_activity) == 1, "on_activity must be wired"


@pytest.mark.asyncio
async def test_scrape_one_marketplace_opens_cm_under_parent_id(monkeypatch):
    child_id = uuid4()
    parent_id = uuid4()
    mp_id = uuid4()

    pending_job = MagicMock()
    pending_job.id = child_id
    pending_job.status = "pending"
    pending_job.marketplace_id = mp_id
    pending_job.parent_job_id = parent_id

    marketplace = MagicMock()
    marketplace.id = mp_id
    marketplace.marketplace_code = "rozetka_com_ua"

    _wire_session_factory(
        monkeypatch, get_results=[pending_job, marketplace]
    )

    cm_calls: list[UUID] = []

    @contextmanager
    def fake_cm(job_id: UUID):
        cm_calls.append(job_id)
        yield

    monkeypatch.setattr(scraper_tasks, "pipeline_worker_log_relay", fake_cm)

    monkeypatch.setattr(
        scraper_tasks,
        "_run_scrape_all_pool",
        lambda *a, **kw: {"scraped_ok": 1, "scraped_failed": 0},
    )

    out = scraper_tasks.scrape_one_marketplace.run(str(child_id))

    assert out["scraped_ok"] == 1
    assert cm_calls == [parent_id]


@pytest.mark.asyncio
async def test_phase1_recon_emits_periodic_heartbeat(monkeypatch):
    """Phase-1 BFS must emit an ``_emit_activity`` line every Nth iteration
    (counter-gated, NOT per-fetch). With BFS_EMIT_EVERY=25, a 50-iteration
    walk yields 2 heartbeat emits.
    """
    from app.modules.scraper.discovery import DiscoveryCrawler

    captured: list[str] = []

    async def on_activity(line: str) -> None:
        captured.append(line)

    db = MagicMock()
    db.flush = AsyncMock()

    pool = MagicMock()
    # Each fetch returns an empty soup-like object; classifier returns "hub"
    # so BFS keeps appending links and visits each URL once.
    soup_stub = MagicMock()

    async def fake_scrape(url, **kwargs):
        return ("<html></html>", soup_stub)

    pool.scrape_page_for_analysis = AsyncMock(side_effect=fake_scrape)

    crawler = DiscoveryCrawler(db, pool, on_activity=on_activity)

    # Drive 30 iterations (above the 25 emit cadence): preload the queue with
    # 30 distinct URLs at depth=0; classifier "unknown" enqueues no children
    # so the BFS just drains the queue without growing it.
    # _phase1_category_recon does local imports — patch on the source modules.
    monkeypatch.setattr(
        "app.modules.classifier.classify_page_role_for_discovery",
        lambda soup, base: "unknown",
    )
    monkeypatch.setattr(
        "app.modules.scraper.extractors.extract_internal_links_all",
        lambda soup, base: [],
    )

    marketplace = MagicMock()
    marketplace.id = uuid4()
    marketplace.base_url = "https://shop.example"
    marketplace.recon_frontier_state = {
        "queue": [[f"https://shop.example/c/{i}", 0] for i in range(30)],
        "visited": [f"https://shop.example/c/{i}" for i in range(30)],
        "listing_urls": [],
    }
    marketplace.discovered_category_urls = []

    # Emulate the model attribute writes the BFS does at the end.
    marketplace.last_category_recon_at = None
    marketplace.category_resume_index = 0

    await crawler._phase1_category_recon(marketplace, deadline_monotonic=None)

    heartbeats = [line for line in captured if "discovery recon" in line]
    # 30 iterations / cadence 25 → exactly one mid-walk heartbeat.
    assert len(heartbeats) == 1
    assert "visited=" in heartbeats[0] and "listing=" in heartbeats[0]


@pytest.mark.asyncio
async def test_emit_activity_noop_without_callback() -> None:
    """If ``on_activity`` is not wired, ``_emit_activity`` is a fast no-op
    (existing contract; pinning so the heartbeat additions don't regress
    callers that don't care about progress).
    """
    from app.modules.scraper.discovery import DiscoveryCrawler

    crawler = DiscoveryCrawler(MagicMock(), MagicMock())
    await crawler._emit_activity("anything")  # must not raise
