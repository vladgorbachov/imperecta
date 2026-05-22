"""Tests for ParsingAdminService contracts and error handling."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest
from sqlalchemy import delete

from app.database import async_session_maker
from app.models.app_tables import ScrapeJob
from app.models.dimensions import DimMarketplace
from app.modules.admin.parsing_admin import ParsingAdminService


@pytest.mark.asyncio
async def test_add_test_marketplaces_is_idempotent():
    """Service creates configured marketplaces once and skips duplicates on rerun."""
    async with async_session_maker() as session:
        service = ParsingAdminService(session)
        domains = [seed.domain for seed in service.TEST_MARKETPLACES]

        await session.execute(delete(DimMarketplace).where(DimMarketplace.domain.in_(domains)))
        await session.commit()

        first = await service.add_test_marketplaces()
        second = await service.add_test_marketplaces()

        assert first["total_requested"] == len(service.TEST_MARKETPLACES)
        assert first["added"] + first["skipped"] == len(service.TEST_MARKETPLACES)
        assert second["added"] == 0
        assert second["skipped"] == len(service.TEST_MARKETPLACES)


@pytest.mark.asyncio
async def test_get_test_marketplaces_contract_shape():
    """Marketplace list response contains strict frontend keys."""
    async with async_session_maker() as session:
        service = ParsingAdminService(session)
        await service.add_test_marketplaces()

        rows = await service.get_test_marketplaces()
        assert isinstance(rows, list)
        assert rows, "Expected at least one test marketplace"
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


@pytest.mark.asyncio
async def test_trigger_full_pipeline_test_returns_constraint_sql_hint():
    """Service returns actionable SQL guidance when job_type constraint blocks full pipeline value."""
    async with async_session_maker() as session:
        service = ParsingAdminService(session)
        with pytest.raises(ValueError) as exc:
            await service.trigger_full_pipeline_test()
        message = str(exc.value)
        assert "Supabase SQL Editor" in message
        assert "full_pipeline_test" in message
        assert "ALTER TABLE scrape_jobs" in message


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

        await session.execute(delete(ScrapeJob).where(ScrapeJob.id == job_id))
        await session.commit()


@pytest.mark.asyncio
async def test_get_job_status_not_found():
    """Unknown job id raises explicit not-found error."""
    async with async_session_maker() as session:
        service = ParsingAdminService(session)
        with pytest.raises(ValueError) as exc:
            await service.get_job_status(UUID("00000000-0000-0000-0000-000000000001"))
        assert "Scrape job not found" in str(exc.value)

