"""Pipeline tests for optional marketplace_code scoping (no hardcoded store names)."""

from __future__ import annotations

from uuid import UUID

import pytest
from sqlalchemy import delete, select

from app.database import async_session_maker
from app.models.app_tables import ScrapeJob
from app.models.dimensions import DimMarketplace
from app.modules.admin.parsing_admin import ParsingAdminService
from app.modules.scraper.pipeline.metadata_store import PipelineMetadataStore


async def _active_marketplace_codes(limit: int = 2) -> list[str]:
    async with async_session_maker() as session:
        result = await session.execute(
            select(DimMarketplace.marketplace_code)
            .where(DimMarketplace.is_active.is_(True))
            .order_by(DimMarketplace.marketplace_code.asc())
            .limit(limit),
        )
        return [row[0] for row in result.all() if row[0]]


@pytest.mark.asyncio
async def test_trigger_full_pipeline_stores_marketplace_codes_in_metadata():
    """Admin trigger persists optional marketplace filter on the parent job."""
    codes = await _active_marketplace_codes(2)
    if not codes:
        pytest.skip("No active marketplaces in database")

    async with async_session_maker() as session:
        service = ParsingAdminService(session)
        created = await service.trigger_full_pipeline_test(marketplace_codes=codes)
        job_id = UUID(created["job_id"])
        job = await session.get(ScrapeJob, job_id)
        assert job is not None
        metadata = PipelineMetadataStore.extract(job.config)
        assert metadata.get("marketplace_codes") == codes
        assert metadata.get("current_stage") == "dispatching"

        await session.execute(delete(ScrapeJob).where(ScrapeJob.id == job_id))
        await session.commit()
