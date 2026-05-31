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


@pytest.mark.asyncio
async def test_filter_urls_by_role_empty():
    from unittest.mock import MagicMock

    crawler = disc.DiscoveryCrawler(MagicMock(), MagicMock())
    accepted, stats = await crawler._filter_urls_by_role([])
    assert accepted == []
    assert stats["mode"] == "empty"


@pytest.mark.asyncio
async def test_filter_urls_by_role_full_mode():
    from unittest.mock import AsyncMock, MagicMock

    crawler = disc.DiscoveryCrawler(MagicMock(), MagicMock())
    roles = {
        "https://shop.example/p/1": "product",
        "https://shop.example/p/2": "listing",
        "https://shop.example/p/3": "product",
    }
    crawler._classify_url = AsyncMock(side_effect=lambda url: roles[url])

    accepted, stats = await crawler._filter_urls_by_role(list(roles))
    assert stats["mode"] == "full"
    assert len(accepted) == 2
    assert stats["accepted"] == 2


@pytest.mark.asyncio
async def test_filter_urls_by_role_trust_sample(monkeypatch):
    from unittest.mock import AsyncMock, MagicMock

    crawler = disc.DiscoveryCrawler(MagicMock(), MagicMock())
    urls = [f"https://shop.example/p/{index}" for index in range(150)]
    crawler._classify_url = AsyncMock(return_value="product")
    monkeypatch.setattr(disc.random, "sample", lambda population, k: population[:k])

    accepted, stats = await crawler._filter_urls_by_role(urls)
    assert stats["mode"] == "trust_sample"
    assert len(accepted) == 150


@pytest.mark.asyncio
async def test_filter_urls_by_role_reject_sample(monkeypatch):
    from unittest.mock import AsyncMock, MagicMock

    crawler = disc.DiscoveryCrawler(MagicMock(), MagicMock())
    urls = [f"https://shop.example/page/{index}" for index in range(150)]
    call_count = 0

    async def classify_side_effect(_url: str) -> str:
        nonlocal call_count
        call_count += 1
        return "product" if call_count == 3 else "hub"

    crawler._classify_url = AsyncMock(side_effect=classify_side_effect)
    monkeypatch.setattr(disc.random, "sample", lambda population, k: population[:k])

    accepted, stats = await crawler._filter_urls_by_role(urls)
    assert stats["mode"] == "reject_sample"
    assert len(accepted) == 1
