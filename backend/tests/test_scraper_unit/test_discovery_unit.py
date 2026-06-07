"""Unit tests for discovery helpers (pure functions + dataclass)."""

import asyncio
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

import app.modules.scraper.discovery as disc
from app.models.dimensions import DimMarketplace


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
    db.commit = AsyncMock()

    crawler = disc.DiscoveryCrawler(db, MagicMock())
    new_count, next_offset, exhausted = await crawler._save_product_urls(
        mp_id,
        [
            "https://unique-shop.example/p/unique-12345",
            "https://unique-shop.example/p/other-67890",
        ],
    )
    assert new_count == 2
    assert next_offset == 2
    assert exhausted is False
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
    db.commit = AsyncMock()

    crawler = disc.DiscoveryCrawler(db, MagicMock())
    new_count, next_offset, exhausted = await crawler._save_product_urls(mp_id, [url])
    assert new_count == 0
    assert next_offset == 1
    assert exhausted is False
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


def _make_mock_db_for_save(existing_hashes: list = None) -> AsyncMock:
    """Build an AsyncMock AsyncSession suitable for _save_product_urls calls."""
    db = AsyncMock()
    existing_result = MagicMock()
    existing_result.all.return_value = [(h,) for h in (existing_hashes or [])]
    db.execute = AsyncMock(return_value=existing_result)
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.flush = AsyncMock()
    return db


def _make_marketplace(**overrides) -> DimMarketplace:
    """Build a minimal DimMarketplace ORM instance (not session-attached)."""
    defaults = dict(
        id=uuid4(),
        marketplace_code="test-mp",
        domain="test-mp.example",
        base_url="https://test-mp.example",
        is_active=True,
        product_quota=0,
        sitemap_resume_offset=0,
        discovered_category_urls=[],
        discovery_error_count=0,
    )
    defaults.update(overrides)
    mp = DimMarketplace(**defaults)
    return mp


class TestResumableSitemap:
    """Cooperative deadline + resumable sitemap offset behavior."""

    @pytest.mark.asyncio
    async def test_save_product_urls_respects_deadline(self):
        mp_id = uuid4()
        db = _make_mock_db_for_save()

        async def slow_commit():
            await asyncio.sleep(0.3)

        db.commit = AsyncMock(side_effect=slow_commit)
        urls = [f"https://shop.example/p/item-{i}" for i in range(1500)]

        crawler = disc.DiscoveryCrawler(db, MagicMock())
        deadline = time.monotonic() + 0.5
        new_count, next_offset, exhausted = await crawler._save_product_urls(
            mp_id, urls, deadline_monotonic=deadline,
        )

        assert exhausted is True
        assert next_offset == disc.SAVE_PRODUCT_URLS_BATCH_SIZE
        assert new_count == disc.SAVE_PRODUCT_URLS_BATCH_SIZE
        assert db.commit.await_count >= 1

    @pytest.mark.asyncio
    async def test_save_product_urls_resumes_from_offset(self):
        mp_id = uuid4()
        db = _make_mock_db_for_save()
        urls = [f"https://shop.example/p/item-{i}" for i in range(1000)]

        crawler = disc.DiscoveryCrawler(db, MagicMock())
        new_count, next_offset, exhausted = await crawler._save_product_urls(
            mp_id, urls, start_offset=500,
        )

        assert new_count == 500
        assert next_offset == 1000
        assert exhausted is False
        product_adds = [
            call for call in db.add.call_args_list
            if isinstance(call.args[0], disc.DimProduct)
        ]
        assert len(product_adds) == 500

    @pytest.mark.asyncio
    async def test_discover_persists_sitemap_resume_offset_on_partial(self):
        mp = _make_marketplace(sitemap_resume_offset=0)
        urls = [f"https://shop.example/p/item-{i}" for i in range(2000)]

        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.flush = AsyncMock()
        db.rollback = AsyncMock()
        db.scalar = AsyncMock(return_value=0)

        crawler = disc.DiscoveryCrawler(db, MagicMock())

        with patch.object(
            disc.DiscoveryCrawler,
            "_phase0_sitemap_harvest",
            new_callable=AsyncMock,
            return_value=urls,
        ), patch.object(
            disc.DiscoveryCrawler,
            "_save_product_urls",
            new_callable=AsyncMock,
            return_value=(300, 800, True),
        ):
            deadline = time.monotonic() + 60
            result = await crawler.discover(mp, deadline_monotonic=deadline)

        assert mp.sitemap_resume_offset == 800
        assert result.status == "partial_budget"
        added_jobs = [
            call.args[0] for call in db.add.call_args_list
            if isinstance(call.args[0], disc.ScrapeJob)
        ]
        assert added_jobs and added_jobs[0].status == "partial"

    @pytest.mark.asyncio
    async def test_discover_resets_offset_on_completion(self):
        mp = _make_marketplace(sitemap_resume_offset=150)
        urls = [f"https://shop.example/p/item-{i}" for i in range(200)]

        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.flush = AsyncMock()
        db.rollback = AsyncMock()
        db.scalar = AsyncMock(return_value=0)

        crawler = disc.DiscoveryCrawler(db, MagicMock())

        with patch.object(
            disc.DiscoveryCrawler,
            "_phase0_sitemap_harvest",
            new_callable=AsyncMock,
            return_value=urls,
        ), patch.object(
            disc.DiscoveryCrawler,
            "_save_product_urls",
            new_callable=AsyncMock,
            return_value=(200, 200, False),
        ):
            result = await crawler.discover(mp)

        assert mp.sitemap_resume_offset == 0
        assert result.status == "completed"

    def test_should_run_sitemap_harvest_with_offset(self):
        crawler = disc.DiscoveryCrawler(MagicMock(), MagicMock())
        recent_dt = datetime.now(timezone.utc) - timedelta(hours=1)

        mp_fresh = _make_marketplace(
            last_sitemap_harvest_at=recent_dt, sitemap_resume_offset=0,
        )
        assert crawler._should_run_sitemap_harvest(mp_fresh) is False

        mp_resume = _make_marketplace(
            last_sitemap_harvest_at=recent_dt, sitemap_resume_offset=500,
        )
        assert crawler._should_run_sitemap_harvest(mp_resume) is True

        mp_never = _make_marketplace(
            last_sitemap_harvest_at=None, sitemap_resume_offset=0,
        )
        assert crawler._should_run_sitemap_harvest(mp_never) is True


class TestPhase2CooperativeDeadline:
    """Cooperative deadline enforcement inside _phase2_product_harvest."""

    def test_headroom_deadline_arithmetic(self):
        assert disc.DiscoveryCrawler._headroom_deadline(None) is None
        with patch("app.modules.scraper.discovery.time.monotonic", return_value=1000.0):
            result = disc.DiscoveryCrawler._headroom_deadline(1100.0)
        assert result == 1000.0 + 100.0 * disc.SAVE_BUDGET_HEADROOM_FRACTION

    @pytest.mark.asyncio
    async def test_phase2_bails_before_fetch_when_deadline_expired(self):
        mp = _make_marketplace()
        pool = MagicMock()
        pool.scrape_page_for_analysis = AsyncMock()
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()

        crawler = disc.DiscoveryCrawler(db, pool)

        with patch(
            "app.modules.scraper.discovery.time.monotonic",
            return_value=5000.0,
        ):
            urls = [f"https://shop.example/c/{i}" for i in range(10)]
            total, exhausted = await crawler._phase2_product_harvest(
                mp, urls, deadline_monotonic=4999.0,
            )

        assert (total, exhausted) == (0, True)
        pool.scrape_page_for_analysis.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_phase2_stops_midway_when_deadline_hits(self):
        mp = _make_marketplace()
        pool = MagicMock()
        from bs4 import BeautifulSoup

        soup = BeautifulSoup("<html></html>", "html.parser")
        pool.scrape_page_for_analysis = AsyncMock(return_value=(None, soup))

        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()

        crawler = disc.DiscoveryCrawler(db, pool)

        clock = {"t": 0.0}

        def fake_monotonic():
            clock["t"] += 5.0
            return clock["t"]

        with patch(
            "app.modules.scraper.discovery.time.monotonic",
            side_effect=fake_monotonic,
        ), patch(
            "app.modules.scraper.extractors.extract_links_from_repeated_structure",
            return_value=["https://shop.example/p/1"],
        ), patch(
            "app.modules.scraper.extractors.detect_next_page",
            return_value=None,
        ), patch.object(
            disc.DiscoveryCrawler,
            "_save_product_urls",
            new_callable=AsyncMock,
            return_value=(1, 1, False),
        ):
            urls = [f"https://shop.example/c/{i}" for i in range(5)]
            total, exhausted = await crawler._phase2_product_harvest(
                mp, urls, deadline_monotonic=20.0,
            )

        assert exhausted is True
        assert pool.scrape_page_for_analysis.await_count < 5

    @pytest.mark.asyncio
    async def test_phase2_completes_without_deadline(self):
        mp = _make_marketplace()
        pool = MagicMock()
        from bs4 import BeautifulSoup

        soup = BeautifulSoup("<html></html>", "html.parser")
        pool.scrape_page_for_analysis = AsyncMock(return_value=(None, soup))

        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()

        crawler = disc.DiscoveryCrawler(db, pool)

        with patch(
            "app.modules.scraper.extractors.extract_links_from_repeated_structure",
            return_value=["https://shop.example/p/x"],
        ), patch(
            "app.modules.scraper.extractors.detect_next_page",
            return_value=None,
        ), patch.object(
            disc.DiscoveryCrawler,
            "_save_product_urls",
            new_callable=AsyncMock,
            return_value=(1, 1, False),
        ):
            urls = [f"https://shop.example/c/{i}" for i in range(3)]
            total, exhausted = await crawler._phase2_product_harvest(mp, urls)

        assert exhausted is False
        assert total == 3
        assert pool.scrape_page_for_analysis.await_count == 3
        assert disc.DiscoveryCrawler._headroom_deadline(None) is None

    @pytest.mark.asyncio
    async def test_discover_category_path_marks_partial_budget(self):
        mp = _make_marketplace(
            discovered_category_urls=[
                "https://shop.example/c/a",
                "https://shop.example/c/b",
            ],
            last_category_recon_at=datetime.now(timezone.utc),
        )
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.flush = AsyncMock()
        db.rollback = AsyncMock()
        db.scalar = AsyncMock(return_value=0)

        crawler = disc.DiscoveryCrawler(db, MagicMock())

        with patch.object(
            disc.DiscoveryCrawler,
            "_phase0_sitemap_harvest",
            new_callable=AsyncMock,
            return_value=[],
        ), patch.object(
            disc.DiscoveryCrawler,
            "_should_run_category_recon",
            return_value=False,
        ), patch.object(
            disc.DiscoveryCrawler,
            "_phase2_product_harvest",
            new_callable=AsyncMock,
            return_value=(7, True),
        ):
            result = await crawler.discover(mp, deadline_monotonic=time.monotonic() + 60)

        assert result.status == "partial_budget"
        added_jobs = [
            call.args[0] for call in db.add.call_args_list
            if isinstance(call.args[0], disc.ScrapeJob)
        ]
        assert added_jobs and added_jobs[0].status == "partial"

    @pytest.mark.asyncio
    async def test_sitemap_path_preserves_headroom(self):
        mp = _make_marketplace()
        urls = [f"https://shop.example/p/{i}" for i in range(20)]

        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.flush = AsyncMock()
        db.rollback = AsyncMock()
        db.scalar = AsyncMock(return_value=0)

        crawler = disc.DiscoveryCrawler(db, MagicMock())
        captured: dict = {}

        async def capture_save(_mp_id, _batch, *, start_offset=0, deadline_monotonic=None):
            captured["deadline_monotonic"] = deadline_monotonic
            return (20, 20, False)

        with patch.object(
            disc.DiscoveryCrawler,
            "_phase0_sitemap_harvest",
            new_callable=AsyncMock,
            return_value=urls,
        ), patch.object(
            disc.DiscoveryCrawler,
            "_save_product_urls",
            side_effect=capture_save,
        ), patch(
            "app.modules.scraper.discovery.time.monotonic",
            return_value=1000.0,
        ):
            await crawler.discover(mp, deadline_monotonic=1100.0)

        expected = 1000.0 + 100.0 * disc.SAVE_BUDGET_HEADROOM_FRACTION
        assert captured["deadline_monotonic"] == expected
