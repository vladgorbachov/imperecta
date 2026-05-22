"""Tests for full pipeline task metadata finalization."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from app.database import async_session_maker
from app.models.app_tables import ScrapeJob, ScrapeLog
from app.models.dimensions import DimMarketplace, DimProduct
from app.models.facts import FactListing
from app.modules.scraper.tasks import _finalize_full_pipeline_job


@pytest.mark.asyncio
async def test_finalize_full_pipeline_job_updates_metadata_and_duration():
    """Finalizer writes timings/summary/per_marketplace and job status fields."""
    async with async_session_maker() as session:
        marketplace = await session.scalar(
            select(DimMarketplace)
            .where(DimMarketplace.is_active.is_(True))
            .order_by(DimMarketplace.created_at.asc())
            .limit(1)
        )
        if marketplace is None:
            pytest.skip("No active marketplace found in dim_marketplace")

        product = DimProduct(name="Pipeline Product", name_normalized="pipeline product", is_active=True)
        session.add(product)
        await session.flush()

        listing = FactListing(
            product_id=product.id,
            marketplace_id=marketplace.id,
            external_url=f"{marketplace.base_url.rstrip('/')}/pipeline-test",
            url_hash=FactListing.compute_url_hash(f"{marketplace.base_url.rstrip('/')}/pipeline-test"),
            is_active=True,
        )
        session.add(listing)
        await session.flush()

        job = ScrapeJob(
            job_type="manual",
            status="running",
            started_at=datetime.now(UTC),
            config={"metadata": {"current_stage": "scrape"}},
        )
        session.add(job)
        await session.flush()

        session.add(
            ScrapeLog(
                scrape_job_id=job.id,
                listing_id=listing.id,
                marketplace_id=marketplace.id,
                status="success",
                url=listing.external_url,
                price_found=100.0,
            )
        )
        session.add(
            ScrapeLog(
                scrape_job_id=job.id,
                listing_id=listing.id,
                marketplace_id=marketplace.id,
                status="error",
                url=listing.external_url,
                error_message="test error",
            )
        )
        await session.commit()

        metadata = await _finalize_full_pipeline_job(
            session,
            job,
            discovery_ms=1200,
            scrape_ms=3400,
            persist_ms=400,
            per_marketplace_seed={
                marketplace.id: {
                    "marketplace_id": str(marketplace.id),
                    "domain": marketplace.domain,
                    "listings_created": 3,
                    "prices_saved": 0,
                    "errors_count": 0,
                    "duration_ms": 2000,
                    "status": "completed",
                }
            },
            hard_error=None,
        )

        assert metadata["timings"]["discovery_ms"] == 1200
        assert metadata["timings"]["scrape_ms"] == 3400
        assert metadata["timings"]["persist_ms"] == 400
        assert metadata["timings"]["total_ms"] == 5000
        assert metadata["summary"]["listings_created"] == 3
        assert metadata["summary"]["prices_saved"] == 1
        assert metadata["summary"]["errors_count"] == 1
        assert len(metadata["per_marketplace"]) == 1
        assert metadata["per_marketplace"][0]["domain"] == marketplace.domain

        refreshed = await session.get(ScrapeJob, job.id)
        assert refreshed is not None
        assert refreshed.status == "completed"
        assert refreshed.duration_ms == 5000
        assert refreshed.completed_at is not None
