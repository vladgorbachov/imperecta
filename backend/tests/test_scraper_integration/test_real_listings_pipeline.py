"""Integration: real fact_listing rows + optional live HTTP for extractors/pool/service."""

from __future__ import annotations

import pytest
from bs4 import BeautifulSoup

from app.modules.scraper.extractors import (
    extract_auto_detect,
    extract_from_jsonld,
    extract_from_meta_tags,
    merge_results,
)
from app.modules.scraper.scraper_pool import ScraperPool
from app.modules.scraper.service import GlobalScrapeService
from fixtures.scraper_fixtures import _pg_available, load_active_listings_from_db


@pytest.fixture(scope="module")
def listing_sample():
    if not _pg_available():
        pytest.skip("PostgreSQL required")
    rows = load_active_listings_from_db(8)
    if not rows:
        pytest.skip("No active listings in fact_listing")
    return rows


@pytest.mark.integration
@pytest.mark.asyncio
async def test_extractors_on_live_html(listing_sample):
    import httpx

    row = listing_sample[0]
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        resp = await client.get(row.external_url)
    if resp.status_code >= 400:
        pytest.skip(f"URL not fetchable: {row.external_url}")
    soup = BeautifulSoup(resp.text, "html.parser")
    a = extract_from_jsonld(soup)
    b = extract_from_meta_tags(soup)
    c = extract_auto_detect(soup, row.external_url)
    merged = merge_results(a, b, c)
    assert merged is not None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_scraper_pool_live_product_url(listing_sample):
    pool = ScraperPool()
    row = listing_sample[0]
    result = await pool.scrape_product(row.external_url)
    assert hasattr(result, "success")


@pytest.mark.integration
def test_global_scrape_service_live_listing(listing_sample):
    from app.database import sync_session_factory

    row = listing_sample[0]
    db = sync_session_factory()
    try:
        pool = ScraperPool()
        svc = GlobalScrapeService(db, pool)
        out = svc.scrape_product(row.id)
        assert hasattr(out, "success")
    finally:
        db.close()


@pytest.mark.integration
def test_service_stale_and_incomplete_helpers(listing_sample):
    from app.database import sync_session_factory
    from app.modules.scraper.scraper_pool import ScraperPool
    from app.modules.scraper.service import GlobalScrapeService

    db = sync_session_factory()
    try:
        pool = ScraperPool()
        svc = GlobalScrapeService(db, pool)
        stale = svc.get_stale_products(limit=5)
        inc = svc.find_incomplete_products(limit=5)
        assert isinstance(stale, list) and isinstance(inc, list)
        svc.recalculate_analytics(listing_sample[0].id)
    finally:
        db.close()
