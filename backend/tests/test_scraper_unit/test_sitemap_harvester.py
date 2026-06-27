"""Unit tests for discovery sitemap_harvester (DB/network-free)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.modules.discovery import cursor_store, sitemap_harvester
from app.models.dimensions import DimMarketplace
from app.modules.discovery.sitemap_harvester import (
    SITEMAP_BAD_HARVEST_RETRY_HOURS,
    SITEMAP_MIN_USEFUL_URLS,
    SITEMAP_STALE_DAYS,
)


def _make_marketplace(**overrides) -> DimMarketplace:
    defaults = dict(
        id=__import__("uuid").uuid4(),
        marketplace_code="test-mp",
        domain="test-mp.example",
        base_url="https://test-mp.example",
        is_active=True,
        locale=None,
        last_sitemap_harvest_at=None,
        sitemap_url=None,
    )
    defaults.update(overrides)
    return DimMarketplace(**defaults)


@pytest.mark.asyncio
async def test_harvest_sitemap_useful_sets_fresh_cooldown_and_returns_products() -> None:
    mp = _make_marketplace()
    pool = MagicMock()
    pool.fetch_sitemap_candidates = AsyncMock(
        return_value=[f"https://test-mp.example/p/{i}" for i in range(12)],
    )
    db = AsyncMock()
    db.flush = AsyncMock()

    product_urls = [f"https://test-mp.example/product/{i}" for i in range(12)]

    async def fake_filter(urls, *, requires_js, scrape_tier, marketplace_locale=None):
        return product_urls, {"mode": "full", "accepted": len(product_urls)}

    result = await sitemap_harvester.harvest_sitemap(
        mp,
        pool,
        db,
        filter_urls_by_role=fake_filter,
    )

    assert result == product_urls
    assert len(result) >= SITEMAP_MIN_USEFUL_URLS
    assert cursor_store.get_last_sitemap_harvest_at(mp) is not None
    assert cursor_store.get_sitemap_url(mp) == "https://test-mp.example/sitemap.xml"
    pool.fetch_sitemap_candidates.assert_awaited_once_with(
        mp.base_url,
        marketplace_locale=mp.locale,
    )
    db.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_harvest_sitemap_not_useful_applies_retry_offset() -> None:
    mp = _make_marketplace(sitemap_url="https://test-mp.example/old-sitemap.xml")
    pool = MagicMock()
    pool.fetch_sitemap_candidates = AsyncMock(
        return_value=[f"https://test-mp.example/p/{i}" for i in range(5)],
    )
    db = AsyncMock()
    db.flush = AsyncMock()
    before = datetime.now(timezone.utc)

    few_products = [f"https://test-mp.example/product/{i}" for i in range(3)]

    async def fake_filter(urls, *, requires_js, scrape_tier, marketplace_locale=None):
        return few_products, {"mode": "full", "accepted": len(few_products)}

    result = await sitemap_harvester.harvest_sitemap(
        mp,
        pool,
        db,
        filter_urls_by_role=fake_filter,
    )

    assert result == few_products
    assert len(result) < SITEMAP_MIN_USEFUL_URLS
    assert cursor_store.get_sitemap_url(mp) == "https://test-mp.example/old-sitemap.xml"
    harvest_at = cursor_store.get_last_sitemap_harvest_at(mp)
    assert harvest_at is not None
    expected_offset = timedelta(
        days=SITEMAP_STALE_DAYS,
        hours=-SITEMAP_BAD_HARVEST_RETRY_HOURS,
    )
    assert harvest_at < before - expected_offset + timedelta(seconds=5)
    assert harvest_at > before - expected_offset - timedelta(seconds=5)
