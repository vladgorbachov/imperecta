"""Pipeline tests scoped to marketplace-style targets (codes only in tests)."""

from __future__ import annotations

from uuid import UUID

import pytest
from sqlalchemy import delete, select

from app.database import async_session_maker
from app.models.app_tables import ScrapeJob
from app.models.dimensions import DimMarketplace
from app.modules.admin.parsing_admin import ParsingAdminService
from app.modules.scraper.pipeline.metadata_store import PipelineMetadataStore

# Hardcoded only in tests — not used in application runtime code.
FOCUS_MARKETPLACE_CODES = (
    "rozetka_com_ua",
    "bomba_md",
    "pandashop_md",
    "musicshop_md",
)


@pytest.mark.asyncio
async def test_trigger_full_pipeline_stores_marketplace_codes_in_metadata():
    """Admin trigger persists optional marketplace filter on the parent job."""
    async with async_session_maker() as session:
        service = ParsingAdminService(session)
        created = await service.trigger_full_pipeline_test(
            marketplace_codes=list(FOCUS_MARKETPLACE_CODES),
        )
        job_id = UUID(created["job_id"])
        job = await session.get(ScrapeJob, job_id)
        assert job is not None
        metadata = PipelineMetadataStore.extract(job.config)
        assert metadata.get("marketplace_codes") == list(FOCUS_MARKETPLACE_CODES)
        assert metadata.get("current_stage") == "dispatching"

        await session.execute(delete(ScrapeJob).where(ScrapeJob.id == job_id))
        await session.commit()


@pytest.mark.asyncio
async def test_focus_marketplace_codes_exist_in_database():
    """Focus codes used in tests must exist as active dim_marketplace rows."""
    async with async_session_maker() as session:
        result = await session.execute(
            select(DimMarketplace.marketplace_code).where(
                DimMarketplace.marketplace_code.in_(FOCUS_MARKETPLACE_CODES)
            )
        )
        found = {row[0] for row in result.all()}
        assert found == set(FOCUS_MARKETPLACE_CODES)


@pytest.mark.asyncio
async def test_999_md_not_in_active_marketplaces():
    """999.md must be removed from the pool, not merely deactivated."""
    async with async_session_maker() as session:
        result = await session.execute(
            select(DimMarketplace).where(DimMarketplace.marketplace_code == "999_md")
        )
        assert result.scalar_one_or_none() is None
