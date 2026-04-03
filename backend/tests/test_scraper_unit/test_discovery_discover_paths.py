"""Unit tests for DiscoveryCrawler.discover (async DB + pool mocked; no fake listing rows)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

import app.modules.scraper.discovery as disc
from app.modules.scraper.scraper_pool import ListingScrapeResult


def _marketplace():
    mp = MagicMock()
    mp.id = uuid4()
    mp.domain = "example.com"
    mp.base_url = "https://example.com/category"
    mp.product_quota = 50
    mp.requires_js = False
    mp.custom_product_link_selector = None
    mp.custom_next_page_selector = None
    return mp


@pytest.mark.asyncio
async def test_discover_completed_saves_urls():
    mp = _marketplace()
    db = MagicMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.flush = AsyncMock()
    # current listings, url_hash check (new), pool count
    db.scalar = AsyncMock(side_effect=[0, None, 3])

    async def scrape_listing(**_kwargs):
        return ListingScrapeResult(
            success=True,
            url="https://example.com/category",
            product_urls=["https://example.com/p/one"],
            next_page_url=None,
            scraper_layer="httpx",
        )

    pool = MagicMock()
    pool.scrape_listing = AsyncMock(side_effect=scrape_listing)

    crawler = disc.DiscoveryCrawler(db, pool)
    res = await crawler.discover(mp)
    assert res.status == "completed"
    assert res.persisted_listings >= 1
    assert res.pages_scanned == 1
    db.commit.assert_called()


@pytest.mark.asyncio
async def test_discover_listing_fetch_failed():
    mp = _marketplace()
    db = MagicMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.scalar = AsyncMock(return_value=0)

    pool = MagicMock()
    pool.scrape_listing = AsyncMock(
        return_value=ListingScrapeResult(
            success=False,
            url=mp.base_url,
            error="fetch_failed",
        ),
    )

    crawler = disc.DiscoveryCrawler(db, pool)
    res = await crawler.discover(mp)
    assert res.status == "error"
    assert res.errors


@pytest.mark.asyncio
async def test_discover_no_categories_empty_page():
    mp = _marketplace()
    db = MagicMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.scalar = AsyncMock(side_effect=[0, 0])

    pool = MagicMock()
    pool.scrape_listing = AsyncMock(
        return_value=ListingScrapeResult(
            success=True,
            url=mp.base_url,
            product_urls=[],
            next_page_url=None,
        ),
    )

    crawler = disc.DiscoveryCrawler(db, pool)
    res = await crawler.discover(mp)
    assert res.status == "no_categories"


@pytest.mark.asyncio
async def test_discover_partial_second_page_fails():
    mp = _marketplace()
    db = MagicMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.flush = AsyncMock()
    # initial count, url_hash miss, final pool count
    db.scalar = AsyncMock(side_effect=[0, None, 1])

    calls = []

    async def scrape_listing(**kwargs):
        calls.append(kwargs.get("url"))
        if len(calls) == 1:
            return ListingScrapeResult(
                success=True,
                url=kwargs["url"],
                product_urls=["https://example.com/p/a"],
                next_page_url="https://example.com/category?page=2",
            )
        return ListingScrapeResult(success=False, url=kwargs["url"], error="down")

    pool = MagicMock()
    pool.scrape_listing = AsyncMock(side_effect=scrape_listing)

    crawler = disc.DiscoveryCrawler(db, pool)
    res = await crawler.discover(mp)
    assert res.status == "partial"
    assert res.persisted_listings >= 1
    assert len(res.errors) >= 1


@pytest.mark.asyncio
async def test_discover_inner_exception_scalar_in_try():
    """Failure inside inner try (e.g. scalar) is caught; status error."""
    mp = _marketplace()
    db = MagicMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.rollback = AsyncMock()
    db.scalar = AsyncMock(side_effect=RuntimeError("scalar boom"))

    pool = MagicMock()

    crawler = disc.DiscoveryCrawler(db, pool)
    res = await crawler.discover(mp)
    assert res.status == "error"


@pytest.mark.asyncio
async def test_discover_success_path_final_commit_raises():
    """Second commit (end of try) fails; except block runs."""
    mp = _marketplace()
    db = MagicMock()
    db.add = MagicMock()
    n = 0

    async def commit_side():
        nonlocal n
        n += 1
        if n == 2:
            raise RuntimeError("final commit")

    db.commit = AsyncMock(side_effect=commit_side)
    db.refresh = AsyncMock()
    db.rollback = AsyncMock()
    db.flush = AsyncMock()

    pool = MagicMock()
    pool.scrape_listing = AsyncMock(
        return_value=ListingScrapeResult(
            success=True,
            url=mp.base_url,
            product_urls=["https://example.com/p/q"],
            next_page_url=None,
        ),
    )
    db.scalar = AsyncMock(side_effect=[0, None, 1])

    crawler = disc.DiscoveryCrawler(db, pool)
    res = await crawler.discover(mp)
    assert res.status == "error"


@pytest.mark.asyncio
async def test_discover_seed_url_https_prefix_from_domain():
    mp = MagicMock()
    mp.id = uuid4()
    mp.domain = "shop.example.org"
    mp.base_url = ""
    mp.product_quota = 10
    mp.requires_js = False
    mp.custom_product_link_selector = None
    mp.custom_next_page_selector = None

    db = MagicMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.flush = AsyncMock()
    db.scalar = AsyncMock(side_effect=[0, 0])

    urls_passed = []

    async def capture(url, **_k):
        urls_passed.append(url)
        return ListingScrapeResult(
            success=True,
            url=url,
            product_urls=[],
            next_page_url=None,
        )

    pool = MagicMock()
    pool.scrape_listing = AsyncMock(side_effect=capture)

    crawler = disc.DiscoveryCrawler(db, pool)
    res = await crawler.discover(mp)
    assert res.status == "no_categories"
    assert urls_passed and str(urls_passed[0]).startswith("https://")
