"""Unit tests for discovery helpers (pure functions + dataclass)."""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

import app.modules.scraper.discovery as disc


def test_title_from_url_and_normalize():
    assert "my product name" in disc._title_from_url("https://shop.example/path/my-product-name")
    assert disc._normalize_name("  Hello   World  ") == "hello world"


def test_discovery_result_dataclass():
    mid = uuid4()
    now = datetime.now(timezone.utc)
    r = disc.DiscoveryResult(
        marketplace_id=mid,
        status="completed",
        started_at=now,
        completed_at=now,
        pages_scanned=1,
        persisted_listings=0,
    )
    assert r.marketplace_id == mid and r.discovery_method == "category_crawl"


@pytest.mark.asyncio
async def test_save_product_urls_creates_new_rows():
    """_save_product_urls persists new URLs when url_hash is not present."""
    from unittest.mock import AsyncMock, MagicMock

    mp_id = uuid4()
    db = AsyncMock()
    existing = MagicMock()
    existing.all.return_value = []
    db.execute = AsyncMock(return_value=existing)
    db.add = MagicMock()
    db.flush = AsyncMock()

    crawler = disc.DiscoveryCrawler(db, MagicMock())
    count = await crawler._save_product_urls(
        mp_id,
        [
            "https://unique-shop.example/p/unique-12345",
            "https://unique-shop.example/p/other-67890",
        ],
    )
    assert count == 2
    assert db.add.call_count >= 2


@pytest.mark.asyncio
async def test_save_product_urls_skips_duplicate_hash():
    from unittest.mock import AsyncMock, MagicMock

    mp_id = uuid4()
    url = "https://shop.example/p/exists"
    url_hash = disc.FactListing.compute_url_hash(url)
    db = AsyncMock()
    existing = MagicMock()
    existing.all.return_value = [(url_hash,)]
    db.execute = AsyncMock(return_value=existing)
    db.add = MagicMock()
    db.flush = AsyncMock()

    crawler = disc.DiscoveryCrawler(db, MagicMock())
    count = await crawler._save_product_urls(mp_id, [url])
    assert count == 0
    db.add.assert_not_called()
