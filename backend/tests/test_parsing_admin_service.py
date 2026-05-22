"""Tests for ParsingAdminService contracts and error handling."""

from __future__ import annotations

from datetime import UTC, datetime
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
        assert running["metadata"] is None

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

