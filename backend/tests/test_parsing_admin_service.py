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

