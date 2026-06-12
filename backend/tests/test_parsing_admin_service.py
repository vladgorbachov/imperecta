"""Tests for ParsingAdminService contracts and error handling."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from app.database import async_session_maker
from app.models.app_tables import ScrapeJob
from app.modules.admin.parsing_admin import ParsingAdminService


@pytest.mark.asyncio
async def test_get_test_marketplaces_contract_shape():
    """Marketplace list response contains strict frontend keys."""
    async with async_session_maker() as session:
        service = ParsingAdminService(session)

        rows = await service.get_test_marketplaces()
        assert isinstance(rows, list)
        expected_keys = {
            "name",
            "url",
            "products_in_pool",
            "last_successful_scrape",
            "success_rate",
            "last_run",
            "status",
        }
        for item in rows:
            assert set(item.keys()) == expected_keys
            assert item["status"] in {"running", "completed", "failed"}
            assert isinstance(item["success_rate"], float)


@pytest.mark.asyncio
async def test_trigger_full_pipeline_test_auto_repairs_constraint():
    """Service creates job and auto-repairs stale job_type constraint when needed."""
    async with async_session_maker() as session:
        service = ParsingAdminService(session)
        created = await service.trigger_full_pipeline_test()
        job_id = UUID(created["job_id"])
        assert created["started_at"] is not None
        job = await session.get(ScrapeJob, job_id)
        if job is not None:
            await session.delete(job)
            await session.commit()


@pytest.mark.asyncio
async def test_trigger_status_and_runs_with_supported_job_type(monkeypatch):
    """When job_type is allowed by schema, service returns poll/status history contracts."""
    async with async_session_maker() as session:
        service = ParsingAdminService(session)
        monkeypatch.setattr(service, "TEST_PIPELINE_JOB_TYPE", "manual")

        created = await service.trigger_full_pipeline_test()
        job_id = UUID(created["job_id"])
        assert created["started_at"] is not None

        running = await service.get_job_status(job_id)
        assert running["status"] == "running"
        assert running["current_stage"] == "queued"
        assert isinstance(running["metadata"], dict)

        job = await session.get(ScrapeJob, job_id)
        assert job is not None
        now = datetime.now(UTC)
        job.status = "completed"
        job.completed_at = now
        job.duration_ms = 2750
        job.config = {
            "metadata": {
                "timings": {
                    "discovery_ms": 500,
                    "scrape_ms": 1000,
                    "persist_ms": 1250,
                    "total_ms": 2750,
                },
                "summary": {
                    "listings_created": 11,
                    "prices_saved": 9,
                    "errors_count": 2,
                },
                "per_marketplace": [],
            }
        }
        await session.commit()

        completed = await service.get_job_status(job_id)
        assert completed["status"] == "completed"
        assert completed["current_stage"] == "completed"
        assert completed["duration_seconds"] == 2.75
        assert completed["metadata"]["summary"]["listings_created"] == 11

        runs = await service.get_test_runs(limit=10)
        assert runs
        latest = runs[0]
        assert latest["job_id"] == str(job_id)
        assert latest["status"] == "completed"
        assert latest["listings_created"] == 11
        assert latest["prices_saved"] == 9
        assert latest["errors_count"] == 2

        await session.delete(job)
        await session.commit()


@pytest.mark.asyncio
async def test_get_test_runs_limit_is_clamped(monkeypatch):
    """Limit values are safely clamped to service bounds."""
    async with async_session_maker() as session:
        service = ParsingAdminService(session)
        monkeypatch.setattr(service, "TEST_PIPELINE_JOB_TYPE", "manual")

        created = await service.trigger_full_pipeline_test()
        job_id = UUID(created["job_id"])

        runs = await service.get_test_runs(limit=0)
        assert runs
        assert runs[0]["job_id"] == str(job_id)

        job = await session.get(ScrapeJob, job_id)
        if job is not None:
            await session.delete(job)
        await session.commit()


@pytest.mark.asyncio
async def test_get_job_status_failed_contains_metadata(monkeypatch):
    """Failed status returns metadata payload for frontend breakdown rendering."""
    async with async_session_maker() as session:
        service = ParsingAdminService(session)
        monkeypatch.setattr(service, "TEST_PIPELINE_JOB_TYPE", "manual")

        created = await service.trigger_full_pipeline_test()
        job_id = UUID(created["job_id"])

        job = await session.get(ScrapeJob, job_id)
        assert job is not None
        job.status = "failed"
        job.completed_at = datetime.now(UTC)
        job.duration_ms = 5100
        job.config = {
            "metadata": {
                "current_stage": "failed",
                "timings": {
                    "discovery_ms": 2000,
                    "scrape_ms": 2500,
                    "persist_ms": 600,
                    "total_ms": 5100,
                },
                "summary": {
                    "listings_created": 5,
                    "prices_saved": 3,
                    "errors_count": 2,
                },
                "per_marketplace": [],
            }
        }
        await session.commit()

        payload = await service.get_job_status(job_id)
        assert payload["status"] == "failed"
        assert payload["current_stage"] == "failed"
        assert payload["metadata"]["timings"]["total_ms"] == 5100
        assert payload["metadata"]["summary"]["errors_count"] == 2

        await session.delete(job)
        await session.commit()


@pytest.mark.asyncio
async def test_get_job_status_not_found():
    """Unknown job id raises explicit not-found error."""
    async with async_session_maker() as session:
        service = ParsingAdminService(session)
        with pytest.raises(ValueError) as exc:
            await service.get_job_status(UUID("00000000-0000-0000-0000-000000000001"))
        assert "Scrape job not found" in str(exc.value)


@pytest.mark.asyncio
async def test_get_job_live_feed_contract_for_empty_job(monkeypatch):
    """Live feed returns stable contract even before any scrape_logs exist."""
    async with async_session_maker() as session:
        service = ParsingAdminService(session)
        monkeypatch.setattr(service, "TEST_PIPELINE_JOB_TYPE", "manual")
        created = await service.trigger_full_pipeline_test()
        job_id = UUID(created["job_id"])

        feed = await service.get_job_live_feed(job_id, limit=50, offset=0)
        assert feed["job_id"] == str(job_id)
        assert isinstance(feed["steps"], list)
        assert isinstance(feed["status_counts"], dict)
        assert "paging" in feed

        job = await session.get(ScrapeJob, job_id)
        if job is not None:
            await session.delete(job)
            await session.commit()


@pytest.mark.asyncio
async def test_get_active_pipeline_job_returns_latest_running(monkeypatch):
    """Active job endpoint helper should return running pipeline row."""
    async with async_session_maker() as session:
        service = ParsingAdminService(session)
        monkeypatch.setattr(service, "TEST_PIPELINE_JOB_TYPE", "manual")

        created = await service.trigger_full_pipeline_test()
        active = await service.get_active_pipeline_job()
        assert active is not None
        assert active["job_id"] == created["job_id"]
        assert active["status"] == "running"

        job = await session.get(ScrapeJob, UUID(created["job_id"]))
        if job is not None:
            await session.delete(job)
            await session.commit()


@pytest.mark.asyncio
async def test_trigger_full_pipeline_test_blocks_parallel_running_job(monkeypatch):
    """Second trigger is rejected while one full-pipeline job is still running."""
    async with async_session_maker() as session:
        service = ParsingAdminService(session)
        monkeypatch.setattr(service, "TEST_PIPELINE_JOB_TYPE", "manual")

        first = await service.trigger_full_pipeline_test()
        with pytest.raises(ValueError) as exc:
            await service.trigger_full_pipeline_test()
        assert "already running" in str(exc.value)

        job = await session.get(ScrapeJob, UUID(first["job_id"]))
        if job is not None:
            await session.delete(job)
            await session.commit()


@pytest.mark.asyncio
async def test_stale_running_pipeline_job_is_marked_failed(monkeypatch):
    """Stale running pipeline jobs are auto-failed before active-job lookup."""
    async with async_session_maker() as session:
        service = ParsingAdminService(session)
        monkeypatch.setattr(service, "TEST_PIPELINE_JOB_TYPE", "manual")
        monkeypatch.setattr(service, "STALE_PIPELINE_TIMEOUT_MINUTES", 1)

        stale_started = datetime.now(UTC) - timedelta(minutes=30)
        stale_job = ScrapeJob(
            job_type="manual",
            status="running",
            started_at=stale_started,
            config={
                "metadata": {
                    "current_stage": "queued",
                    "last_activity_at": (datetime.now(UTC) - timedelta(minutes=20)).isoformat(),
                    "summary": {"listings_created": 0, "prices_saved": 0, "errors_count": 0},
                    "timings": {"discovery_ms": 0, "scrape_ms": 0, "persist_ms": 0, "total_ms": 0},
                    "per_marketplace": [],
                }
            },
        )
        session.add(stale_job)
        await session.commit()

        active = await service.get_active_pipeline_job()
        assert active is None

        refreshed = await session.get(ScrapeJob, stale_job.id)
        assert refreshed is not None
        assert refreshed.status == "failed"
        meta = (refreshed.config or {}).get("metadata") if isinstance(refreshed.config, dict) else {}
        assert isinstance(meta, dict)
        assert meta.get("current_stage") == "failed"
        assert "stale_pipeline_timeout" in str(meta.get("error"))

        await session.delete(refreshed)
        await session.commit()


@pytest.mark.asyncio
async def test_get_test_runs_falls_back_to_job_counters(monkeypatch):
    """History payload falls back to ScrapeJob counters when metadata summary is missing."""
    async with async_session_maker() as session:
        service = ParsingAdminService(session)
        monkeypatch.setattr(service, "TEST_PIPELINE_JOB_TYPE", "manual")

        created = await service.trigger_full_pipeline_test()
        job_id = UUID(created["job_id"])
        job = await session.get(ScrapeJob, job_id)
        assert job is not None
        job.status = "completed"
        job.total_listings = 8
        job.successful = 5
        job.failed = 3
        job.duration_ms = 1300
        job.completed_at = datetime.now(UTC)
        job.config = {}
        await session.commit()

        rows = await service.get_test_runs(limit=10)
        target = next((row for row in rows if row["job_id"] == str(job_id)), None)
        assert target is not None
        assert target["listings_created"] == 8
        assert target["prices_saved"] == 5
        assert target["errors_count"] == 3
        assert target["duration_seconds"] == 1.3

        await session.delete(job)
        await session.commit()


# ---------------------------------------------------------------------------
# Pure staticmethod tests (no DB, no async) for status normalizers.
# Covers 'partial' as a first-class valid status alongside existing values.
# ---------------------------------------------------------------------------


class TestNormalizeJobStatus:
    def test_partial_passes_through(self):
        assert ParsingAdminService._normalize_job_status("partial") == "partial"

    def test_running_completed_failed_pass_through(self):
        assert ParsingAdminService._normalize_job_status("running") == "running"
        assert ParsingAdminService._normalize_job_status("completed") == "completed"
        assert ParsingAdminService._normalize_job_status("failed") == "failed"

    def test_pending_maps_to_running(self):
        assert ParsingAdminService._normalize_job_status("pending") == "running"

    def test_cancelled_collapses_to_failed(self):
        # Regression guard: existing collapse is intentionally unchanged.
        assert ParsingAdminService._normalize_job_status("cancelled") == "failed"

    def test_none_collapses_to_failed(self):
        assert ParsingAdminService._normalize_job_status(None) == "failed"


class TestNormalizeMarketplaceStatus:
    def test_partial_passes_through(self):
        assert (
            ParsingAdminService._normalize_marketplace_status("partial", None)
            == "partial"
        )

    def test_running_completed_failed_pass_through(self):
        assert (
            ParsingAdminService._normalize_marketplace_status("running", None)
            == "running"
        )
        assert (
            ParsingAdminService._normalize_marketplace_status("completed", None)
            == "completed"
        )
        assert (
            ParsingAdminService._normalize_marketplace_status("failed", None)
            == "failed"
        )

    def test_pending_maps_to_running(self):
        assert (
            ParsingAdminService._normalize_marketplace_status("pending", None)
            == "running"
        )

    def test_last_scrape_success_maps_to_completed(self):
        assert (
            ParsingAdminService._normalize_marketplace_status(None, "success")
            == "completed"
        )

    def test_last_scrape_timeout_maps_to_failed(self):
        assert (
            ParsingAdminService._normalize_marketplace_status(None, "timeout")
            == "failed"
        )


class TestToFrontendStatus:
    """Pure mapping from internal status to frontend enum."""

    def test_running_passes_through(self):
        assert ParsingAdminService._to_frontend_status("running") == "running"

    def test_completed_passes_through(self):
        assert ParsingAdminService._to_frontend_status("completed") == "completed"

    def test_partial_maps_to_completed(self):
        assert ParsingAdminService._to_frontend_status("partial") == "completed"

    def test_failed_passes_through(self):
        assert ParsingAdminService._to_frontend_status("failed") == "failed"

    def test_cancelled_collapses_to_failed(self):
        assert ParsingAdminService._to_frontend_status("cancelled") == "failed"


class TestMarketplaceHealth:
    """Pure derivation of health bucket from (success_rate, total_runs).

    Separate from last-run `status`: expresses historical reliability. None
    when total_runs==0 (no signal — must not read as 'failing').
    """

    def test_healthy_at_and_above_80(self):
        assert ParsingAdminService._health_from_success_rate(80.0, 10) == "healthy"
        assert ParsingAdminService._health_from_success_rate(95.0, 10) == "healthy"

    def test_degraded_between_50_and_80(self):
        assert ParsingAdminService._health_from_success_rate(79.99, 10) == "degraded"
        assert ParsingAdminService._health_from_success_rate(50.0, 10) == "degraded"

    def test_failing_below_50(self):
        assert ParsingAdminService._health_from_success_rate(49.99, 10) == "failing"
        assert ParsingAdminService._health_from_success_rate(0.0, 10) == "failing"

    def test_no_runs_is_none_not_failing(self):
        assert ParsingAdminService._health_from_success_rate(0.0, 0) is None
        assert ParsingAdminService._health_from_success_rate(100.0, 0) is None


async def _cleanup_full_pipeline_jobs(session) -> None:
    """Wipe every full_pipeline_test row so latest-job tests see a clean slate."""
    from sqlalchemy import delete as sa_delete

    await session.execute(
        sa_delete(ScrapeJob).where(ScrapeJob.job_type == "manual")
    )
    await session.commit()


@pytest.mark.asyncio
async def test_pipeline_status_running(monkeypatch):
    """Running pipeline → status='running', discovery + job_id populated."""
    async with async_session_maker() as session:
        service = ParsingAdminService(session)
        monkeypatch.setattr(service, "TEST_PIPELINE_JOB_TYPE", "manual")
        await _cleanup_full_pipeline_jobs(session)

        running_job = ScrapeJob(
            job_type="manual",
            status="running",
            started_at=datetime.now(UTC) - timedelta(seconds=30),
            config={
                "metadata": {
                    "current_stage": "discovery",
                    "last_activity_at": datetime.now(UTC).isoformat(),
                    "summary": {"listings_created": 4, "prices_saved": 3, "errors_count": 0},
                    "timings": {"discovery_ms": 0, "scrape_ms": 0, "persist_ms": 0, "total_ms": 0},
                    "per_marketplace": [],
                    "discovery_marketplace_done": 2,
                    "discovery_marketplace_total": 5,
                    "discovery_current_domain": "barbora.lv",
                }
            },
        )
        session.add(running_job)
        await session.commit()

        try:
            payload = await service.get_pipeline_status()
            assert payload["status"] == "running"
            assert payload["job_id"] == str(running_job.id)
            assert payload["current_stage"] in {"discovery", "queued", "scrape", "persist"}
            assert payload["discovery"] == {
                "done": 2,
                "total": 5,
                "current_domain": "barbora.lv",
            }
        finally:
            await session.delete(running_job)
            await session.commit()


@pytest.mark.asyncio
async def test_pipeline_status_latest_completed_when_none_running(monkeypatch):
    """No running job → latest completed terminal job is returned."""
    async with async_session_maker() as session:
        service = ParsingAdminService(session)
        monkeypatch.setattr(service, "TEST_PIPELINE_JOB_TYPE", "manual")
        await _cleanup_full_pipeline_jobs(session)

        started = datetime.now(UTC) - timedelta(minutes=10)
        completed = datetime.now(UTC) - timedelta(minutes=8)
        terminal = ScrapeJob(
            job_type="manual",
            status="completed",
            started_at=started,
            completed_at=completed,
            duration_ms=120_000,
            config={
                "metadata": {
                    "current_stage": "completed",
                    "summary": {
                        "listings_created": 7,
                        "prices_saved": 6,
                        "errors_count": 1,
                    },
                    "timings": {
                        "discovery_ms": 0,
                        "scrape_ms": 0,
                        "persist_ms": 0,
                        "total_ms": 120_000,
                    },
                    "per_marketplace": [],
                }
            },
        )
        session.add(terminal)
        await session.commit()

        try:
            payload = await service.get_pipeline_status()
            assert payload["status"] == "completed"
            assert payload["job_id"] == str(terminal.id)
            assert payload["completed_at"] is not None
            assert payload["duration_seconds"] == 120.0
        finally:
            await session.delete(terminal)
            await session.commit()


@pytest.mark.asyncio
async def test_pipeline_status_partial_maps_to_completed(monkeypatch):
    """Latest 'partial' job collapses to frontend 'completed' while keeping metadata."""
    async with async_session_maker() as session:
        service = ParsingAdminService(session)
        monkeypatch.setattr(service, "TEST_PIPELINE_JOB_TYPE", "manual")
        await _cleanup_full_pipeline_jobs(session)

        partial = ScrapeJob(
            job_type="manual",
            status="partial",
            started_at=datetime.now(UTC) - timedelta(minutes=5),
            completed_at=datetime.now(UTC) - timedelta(minutes=4),
            duration_ms=60_000,
            config={
                "metadata": {
                    "current_stage": "completed",
                    "summary": {
                        "listings_created": 2,
                        "prices_saved": 2,
                        "errors_count": 3,
                    },
                    "timings": {
                        "discovery_ms": 0,
                        "scrape_ms": 0,
                        "persist_ms": 0,
                        "total_ms": 60_000,
                    },
                    "per_marketplace": [
                        {
                            "marketplace_id": "00000000-0000-0000-0000-000000000001",
                            "domain": "barbora.lt",
                            "status": "failed",
                            "listings_created": 0,
                            "prices_saved": 0,
                            "errors_count": 3,
                            "duration_ms": 1000,
                        }
                    ],
                }
            },
        )
        session.add(partial)
        await session.commit()

        try:
            payload = await service.get_pipeline_status()
            assert payload["status"] == "completed"
            assert payload["metadata"]["per_marketplace"][0]["status"] == "failed"
            assert payload["metadata"]["summary"]["errors_count"] == 3
        finally:
            await session.delete(partial)
            await session.commit()


@pytest.mark.asyncio
@pytest.mark.parametrize("raw_status", ["failed", "cancelled"])
async def test_pipeline_status_failed(monkeypatch, raw_status):
    """Latest failed/cancelled job collapses to frontend 'failed'."""
    async with async_session_maker() as session:
        service = ParsingAdminService(session)
        monkeypatch.setattr(service, "TEST_PIPELINE_JOB_TYPE", "manual")
        await _cleanup_full_pipeline_jobs(session)

        job = ScrapeJob(
            job_type="manual",
            status=raw_status,
            started_at=datetime.now(UTC) - timedelta(minutes=2),
            completed_at=datetime.now(UTC) - timedelta(minutes=1),
            duration_ms=30_000,
            config={
                "metadata": {
                    "current_stage": "failed",
                    "summary": {
                        "listings_created": 0,
                        "prices_saved": 0,
                        "errors_count": 1,
                    },
                    "timings": {
                        "discovery_ms": 0,
                        "scrape_ms": 0,
                        "persist_ms": 0,
                        "total_ms": 30_000,
                    },
                    "per_marketplace": [],
                    "error": "boom",
                }
            },
        )
        session.add(job)
        await session.commit()

        try:
            payload = await service.get_pipeline_status()
            assert payload["status"] == "failed"
            assert payload["job_id"] == str(job.id)
        finally:
            await session.delete(job)
            await session.commit()


@pytest.mark.asyncio
async def test_pipeline_status_idle_when_no_jobs(monkeypatch):
    """No pipeline jobs at all → idle payload with zeroed discovery."""
    async with async_session_maker() as session:
        service = ParsingAdminService(session)
        # Use a unique job_type that no real row in the DB carries so we
        # observe the genuine empty case without fabricating fake rows.
        monkeypatch.setattr(service, "TEST_PIPELINE_JOB_TYPE", "__o6_no_such_job_type__")

        payload = await service.get_pipeline_status()
        assert payload == {
            "job_id": None,
            "status": "idle",
            "current_stage": None,
            "started_at": None,
            "completed_at": None,
            "duration_seconds": None,
            "metadata": {},
            "discovery": {"done": 0, "total": 0, "current_domain": None},
        }


@pytest.mark.asyncio
async def test_pipeline_status_calls_stale_reaper(monkeypatch):
    """Parity with get_active_pipeline_job: stale reaper runs before the query."""
    calls: list[str] = []

    async with async_session_maker() as session:
        service = ParsingAdminService(session)
        monkeypatch.setattr(service, "TEST_PIPELINE_JOB_TYPE", "__o6_no_such_job_type__")

        original = service._fail_stale_running_pipeline_jobs

        async def spy() -> None:
            calls.append("reaped")
            await original()

        monkeypatch.setattr(service, "_fail_stale_running_pipeline_jobs", spy)

        await service.get_pipeline_status()
        assert calls == ["reaped"]
