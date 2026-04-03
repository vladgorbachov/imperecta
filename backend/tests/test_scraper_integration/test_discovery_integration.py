"""Integration: DiscoveryCrawler.discover with real DimMarketplace + stubbed pool I/O."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.database import async_session_maker
from app.models.dimensions import DimMarketplace
from app.modules.scraper.discovery import DiscoveryCrawler
from app.modules.scraper.scraper_pool import ListingScrapeResult, ScraperPool
from fixtures.scraper_fixtures import _pg_available


@pytest.mark.integration
@pytest.mark.asyncio
async def test_discover_fails_fast_when_listing_fetch_fails():
    if not _pg_available():
        pytest.skip("PostgreSQL required")
    async with async_session_maker() as db:
        res = await db.execute(select(DimMarketplace).where(DimMarketplace.is_active.is_(True)).limit(1))
        mp = res.scalar_one_or_none()
        if not mp:
            pytest.skip("No active marketplace")

        pool = ScraperPool()

        async def fail_listing(**kwargs):
            return ListingScrapeResult(success=False, url=kwargs.get("url", ""), error="listing_fetch_failed")

        pool.scrape_listing = fail_listing  # type: ignore[method-assign]

        crawler = DiscoveryCrawler(db, pool)
        out = await crawler.discover(mp)
        assert out.status in {"error", "partial"}
        assert out.errors


@pytest.mark.integration
@pytest.mark.asyncio
async def test_discover_exception_path_rollback(monkeypatch):
    if not _pg_available():
        pytest.skip("PostgreSQL required")
    async with async_session_maker() as db:
        res = await db.execute(select(DimMarketplace).where(DimMarketplace.is_active.is_(True)).limit(1))
        mp = res.scalar_one_or_none()
        if not mp:
            pytest.skip("No active marketplace")

        pool = ScraperPool()

        async def boom(**kwargs):
            raise RuntimeError("forced discovery failure")

        pool.scrape_listing = boom  # type: ignore[method-assign]
        crawler = DiscoveryCrawler(db, pool)
        out = await crawler.discover(mp)
        assert out.status == "error"
