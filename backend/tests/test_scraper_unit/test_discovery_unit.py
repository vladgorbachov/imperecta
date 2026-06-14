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
        recon_frontier_state=None,
        category_resume_index=0,
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

        # Deadline is checked once per batch (SAVE_PRODUCT_URLS_BATCH_SIZE
        # URLs == 500), AFTER each commit. With a 0.5s budget and 0.3s/commit,
        # two batches commit (t=0.3 < 0.5 → continue; t=0.6 >= 0.5 → stop), so
        # the resume offset lands at 2 batches. Pinning the per-batch cadence
        # here would catch a regression that moved the deadline check to
        # per-URL — production timing is correct as-is.
        assert exhausted is True
        assert next_offset == 2 * disc.SAVE_PRODUCT_URLS_BATCH_SIZE
        assert new_count == 2 * disc.SAVE_PRODUCT_URLS_BATCH_SIZE
        assert db.commit.await_count >= 2

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
            total, next_index, more = await crawler._phase2_product_harvest(
                mp, urls, deadline_monotonic=4999.0,
            )

        assert total == 0
        assert next_index == 0
        assert more is True
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
            total, next_index, more = await crawler._phase2_product_harvest(
                mp, urls, deadline_monotonic=20.0,
            )

        assert more is True
        assert 0 <= next_index < 5
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
            total, next_index, more = await crawler._phase2_product_harvest(mp, urls)

        assert more is False
        assert next_index == 0
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
            return_value=(7, 2, True),
        ):
            result = await crawler.discover(mp, deadline_monotonic=time.monotonic() + 60)

        assert result.status == "partial_budget"
        assert mp.category_resume_index == 2
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


class TestPhase1FrontierResume:
    """Cooperative deadline + persistent BFS frontier in _phase1."""

    @pytest.mark.asyncio
    async def test_phase1_persists_frontier_on_deadline(self):
        mp = _make_marketplace(recon_frontier_state=None)
        pool = MagicMock()
        pool.scrape_page_for_analysis = AsyncMock()
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.flush = AsyncMock()

        crawler = disc.DiscoveryCrawler(db, pool)

        with patch(
            "app.modules.scraper.discovery.time.monotonic",
            return_value=5000.0,
        ):
            urls, exhausted = await crawler._phase1_category_recon(
                mp, deadline_monotonic=4000.0,
            )

        assert (urls, exhausted) == ([], True)
        assert isinstance(mp.recon_frontier_state, dict)
        assert set(mp.recon_frontier_state.keys()) == {"queue", "visited", "listing_urls"}
        assert [mp.base_url, 0] in mp.recon_frontier_state["queue"]
        assert mp.base_url in mp.recon_frontier_state["visited"]
        pool.scrape_page_for_analysis.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_phase1_resumes_from_saved_frontier(self, caplog):
        mp = _make_marketplace(
            base_url="https://x/",
            recon_frontier_state={
                "queue": [["https://x/a", 1], ["https://x/b", 1]],
                "visited": ["https://x/", "https://x/a", "https://x/b"],
                "listing_urls": ["https://x/cat1"],
            },
        )
        pool = MagicMock()
        pool.scrape_page_for_analysis = AsyncMock(return_value=(None, None))
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.flush = AsyncMock()

        crawler = disc.DiscoveryCrawler(db, pool)

        import logging as _logging
        with caplog.at_level(_logging.INFO, logger="app.modules.scraper.discovery"):
            urls, exhausted = await crawler._phase1_category_recon(
                mp, deadline_monotonic=None,
            )

        first_call_url = pool.scrape_page_for_analysis.call_args_list[0].args[0]
        assert first_call_url == "https://x/a"
        assert (urls, exhausted) == (["https://x/cat1"], False)
        assert mp.recon_frontier_state is None
        messages = " ".join(rec.getMessage() for rec in caplog.records)
        assert "category_recon_resume" in messages
        assert "category_recon_start" not in messages

    @pytest.mark.asyncio
    async def test_phase1_clears_frontier_on_natural_completion(self):
        mp = _make_marketplace(
            base_url="https://x/",
            recon_frontier_state={
                "queue": [],
                "visited": ["https://x/"],
                "listing_urls": [],
            },
        )
        pool = MagicMock()
        pool.scrape_page_for_analysis = AsyncMock(return_value=(None, None))
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.flush = AsyncMock()

        crawler = disc.DiscoveryCrawler(db, pool)
        urls, exhausted = await crawler._phase1_category_recon(
            mp, deadline_monotonic=None,
        )

        assert exhausted is False
        assert mp.recon_frontier_state is None
        assert mp.discovered_category_urls == urls

    def test_should_run_category_recon_with_frontier(self):
        crawler = disc.DiscoveryCrawler(MagicMock(), MagicMock())
        recent = datetime.now(timezone.utc)

        mp_fresh = _make_marketplace(
            discovered_category_urls=["https://x/c1"],
            last_category_recon_at=recent,
            recon_frontier_state=None,
        )
        assert crawler._should_run_category_recon(mp_fresh) is False

        mp_resume = _make_marketplace(
            discovered_category_urls=["https://x/c1"],
            last_category_recon_at=recent,
            recon_frontier_state={"queue": [["https://x/a", 1]]},
        )
        assert crawler._should_run_category_recon(mp_resume) is True

    @pytest.mark.asyncio
    async def test_discover_skips_phase2_when_phase1_exhausted(self):
        mp = _make_marketplace()
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
            return_value=True,
        ), patch.object(
            disc.DiscoveryCrawler,
            "_phase1_category_recon",
            new_callable=AsyncMock,
            return_value=(["u"], True),
        ), patch.object(
            disc.DiscoveryCrawler,
            "_phase2_product_harvest",
            new_callable=AsyncMock,
        ) as phase2_mock:
            result = await crawler.discover(
                mp, deadline_monotonic=time.monotonic() + 60,
            )

        phase2_mock.assert_not_awaited()
        assert result.status == "partial_budget"
        added_jobs = [
            call.args[0] for call in db.add.call_args_list
            if isinstance(call.args[0], disc.ScrapeJob)
        ]
        assert added_jobs and added_jobs[0].status == "partial"

    @pytest.mark.asyncio
    async def test_discover_runs_phase2_when_phase1_completes(self):
        mp = _make_marketplace()
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.flush = AsyncMock()
        db.rollback = AsyncMock()
        db.scalar = AsyncMock(return_value=0)

        crawler = disc.DiscoveryCrawler(db, MagicMock())
        captured: dict = {"phase1": None, "phase2": None}

        async def fake_phase1(_mp, *, deadline_monotonic=None):
            captured["phase1"] = deadline_monotonic
            _mp.discovered_category_urls = ["https://x/c1", "https://x/c2"]
            return (["https://x/c1", "https://x/c2"], False)

        async def fake_phase2(_mp, _urls, *, start_index=0, deadline_monotonic=None):
            captured["phase2"] = deadline_monotonic
            return (4, 0, False)

        with patch.object(
            disc.DiscoveryCrawler,
            "_phase0_sitemap_harvest",
            new_callable=AsyncMock,
            return_value=[],
        ), patch.object(
            disc.DiscoveryCrawler,
            "_should_run_category_recon",
            return_value=True,
        ), patch.object(
            disc.DiscoveryCrawler,
            "_phase1_category_recon",
            side_effect=fake_phase1,
        ), patch.object(
            disc.DiscoveryCrawler,
            "_phase2_product_harvest",
            side_effect=fake_phase2,
        ):
            result = await crawler.discover(
                mp, deadline_monotonic=time.monotonic() + 60,
            )

        assert captured["phase1"] is not None
        assert captured["phase1"] == captured["phase2"]
        assert result.status == "completed"
        assert mp.category_resume_index == 0


class TestPhase2CategoryResume:
    """Cursor state machine for resumable category harvest in _phase2."""

    @staticmethod
    def _setup_crawler_with_soup():
        from bs4 import BeautifulSoup

        soup = BeautifulSoup("<html></html>", "html.parser")
        pool = MagicMock()
        pool.scrape_page_for_analysis = AsyncMock(return_value=(None, soup))
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.flush = AsyncMock()
        crawler = disc.DiscoveryCrawler(db, pool)
        return crawler, pool

    @pytest.mark.asyncio
    async def test_phase2_resumes_from_start_index(self):
        mp = _make_marketplace()
        crawler, pool = self._setup_crawler_with_soup()
        urls = [f"https://shop.example/c/{i}" for i in range(10)]

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
            total, next_index, more = await crawler._phase2_product_harvest(
                mp, urls, start_index=4,
            )

        first_fetched = pool.scrape_page_for_analysis.call_args_list[0].args[0]
        assert first_fetched == urls[4]
        assert next_index == 0
        assert more is False
        assert total > 0

    @pytest.mark.asyncio
    async def test_phase2_deadline_sets_next_index_to_unprocessed(self):
        mp = _make_marketplace()
        crawler, pool = self._setup_crawler_with_soup()
        urls = [f"https://shop.example/c/{i}" for i in range(10)]

        # Each outer category invokes monotonic() for the top deadline check.
        # Inner pagination iterates once per category (detect_next_page=None),
        # so each iteration uses ~2 monotonic() calls.
        # Trip the deadline starting from the 3rd category (absolute_idx=2).
        # Tie monotonic to a counter incremented per outer-loop deadline check
        # via a fresh patch helper that tracks category starts.
        category_starts = {"n": 0}

        def fake_monotonic():
            # 2 monotonic() calls per category (outer + inner deadline checks)
            # with _save_product_urls mocked. Cat 0 uses n=0,1; Cat 1 uses
            # n=2,3; Cat 2 outer is n=4 — fire deadline there so next_index=2.
            n = category_starts["n"]
            category_starts["n"] += 1
            return 0.0 if n < 4 else 10_000.0

        with patch(
            "app.modules.scraper.discovery.time.monotonic",
            side_effect=fake_monotonic,
        ), patch(
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
            total, next_index, more = await crawler._phase2_product_harvest(
                mp, urls, deadline_monotonic=100.0,
            )

        assert more is True
        assert next_index == 2

    @pytest.mark.asyncio
    async def test_phase2_window_cap_signals_more(self):
        mp = _make_marketplace()
        crawler, pool = self._setup_crawler_with_soup()
        cap = disc.MAX_CATEGORY_URLS_PER_RUN
        urls = [f"https://shop.example/c/{i}" for i in range(cap + 5)]

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
            total, next_index, more = await crawler._phase2_product_harvest(
                mp, urls, start_index=0,
            )

        assert next_index == cap
        assert more is True
        assert total == cap

    @pytest.mark.asyncio
    async def test_phase2_convergence_resets_cursor(self):
        mp = _make_marketplace()
        crawler, pool = self._setup_crawler_with_soup()
        streak = disc.CATEGORY_CONVERGENCE_STREAK
        urls = [f"https://shop.example/c/{i}" for i in range(10)]

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
            return_value=(0, 0, False),
        ):
            total, next_index, more = await crawler._phase2_product_harvest(
                mp, urls, start_index=0,
            )

        assert total == 0
        assert next_index == 0
        assert more is False
        # Convergence should fire exactly after `streak` empty categories.
        assert pool.scrape_page_for_analysis.await_count <= streak

    @pytest.mark.asyncio
    async def test_phase2_empty_window_when_list_shrank(self):
        mp = _make_marketplace()
        crawler, pool = self._setup_crawler_with_soup()
        urls = [f"https://shop.example/c/{i}" for i in range(3)]

        total, next_index, more = await crawler._phase2_product_harvest(
            mp, urls, start_index=5,
        )

        assert (total, next_index, more) == (0, 0, False)
        pool.scrape_page_for_analysis.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_discover_persists_category_resume_index_on_partial(self):
        mp = _make_marketplace(
            discovered_category_urls=[f"https://x/c{i}" for i in range(20)],
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
            return_value=(5, 7, True),
        ):
            result = await crawler.discover(
                mp, deadline_monotonic=time.monotonic() + 60,
            )

        assert mp.category_resume_index == 7
        assert result.status == "partial_budget"

    @pytest.mark.asyncio
    async def test_discover_resets_category_index_on_completion(self):
        mp = _make_marketplace(
            discovered_category_urls=[f"https://x/c{i}" for i in range(5)],
            last_category_recon_at=datetime.now(timezone.utc),
            category_resume_index=3,
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
            return_value=(5, 0, False),
        ):
            result = await crawler.discover(
                mp, deadline_monotonic=time.monotonic() + 60,
            )

        assert mp.category_resume_index == 0
        assert result.status == "completed"

    def test_should_run_category_recon_skipped_when_resume_index_set(self):
        crawler = disc.DiscoveryCrawler(MagicMock(), MagicMock())
        recent = datetime.now(timezone.utc)

        mp_mid = _make_marketplace(
            discovered_category_urls=["https://x/c1"],
            last_category_recon_at=recent,
            recon_frontier_state=None,
            category_resume_index=3,
        )
        assert crawler._should_run_category_recon(mp_mid) is False

        mp_done = _make_marketplace(
            discovered_category_urls=["https://x/c1"],
            last_category_recon_at=recent,
            recon_frontier_state=None,
            category_resume_index=0,
        )
        assert crawler._should_run_category_recon(mp_done) is False  # fresh recon

        mp_empty = _make_marketplace(
            discovered_category_urls=[],
            last_category_recon_at=None,
            recon_frontier_state=None,
            category_resume_index=0,
        )
        assert crawler._should_run_category_recon(mp_empty) is True

    @pytest.mark.asyncio
    async def test_phase1_completion_resets_category_index(self):
        mp = _make_marketplace(
            base_url="https://x/",
            recon_frontier_state={
                "queue": [],
                "visited": ["https://x/"],
                "listing_urls": [],
            },
            category_resume_index=4,
        )
        pool = MagicMock()
        pool.scrape_page_for_analysis = AsyncMock(return_value=(None, None))
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.flush = AsyncMock()

        crawler = disc.DiscoveryCrawler(db, pool)
        urls, exhausted = await crawler._phase1_category_recon(
            mp, deadline_monotonic=None,
        )

        assert exhausted is False
        assert mp.category_resume_index == 0


class TestDiscoverParentJobId:
    """O1: discover() accepts + persists optional parent_job_id on inner job."""

    @staticmethod
    def _make_db() -> AsyncMock:
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.flush = AsyncMock()
        db.rollback = AsyncMock()
        db.scalar = AsyncMock(return_value=0)
        return db

    @pytest.mark.asyncio
    async def test_discover_sets_parent_job_id_when_provided(self):
        mp = _make_marketplace(sitemap_resume_offset=0)
        urls = [f"https://shop.example/p/item-{i}" for i in range(10)]
        db = self._make_db()
        parent_id = uuid4()

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
            return_value=(10, 10, False),
        ):
            await crawler.discover(mp, parent_job_id=parent_id)

        added_jobs = [
            call.args[0]
            for call in db.add.call_args_list
            if isinstance(call.args[0], disc.ScrapeJob)
        ]
        assert added_jobs, "expected at least one ScrapeJob to be added"
        assert added_jobs[0].parent_job_id == parent_id

    @pytest.mark.asyncio
    async def test_discover_parent_job_id_defaults_none(self):
        mp = _make_marketplace(sitemap_resume_offset=0)
        urls = [f"https://shop.example/p/item-{i}" for i in range(10)]
        db = self._make_db()

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
            return_value=(10, 10, False),
        ):
            await crawler.discover(mp)

        added_jobs = [
            call.args[0]
            for call in db.add.call_args_list
            if isinstance(call.args[0], disc.ScrapeJob)
        ]
        assert added_jobs, "expected at least one ScrapeJob to be added"
        assert added_jobs[0].parent_job_id is None

    def test_scrape_job_parent_fk_nullable(self):
        from app.models.app_tables import ScrapeJob

        job_no_parent = ScrapeJob(job_type="discovery", status="running")
        assert job_no_parent.parent_job_id is None

        parent_id = uuid4()
        job_with_parent = ScrapeJob(
            job_type="discovery",
            status="running",
            parent_job_id=parent_id,
        )
        assert job_with_parent.parent_job_id == parent_id


class TestDiscoverInnerJobOwnership:
    """O2: discover() owns a pre-created inner ScrapeJob instead of inserting."""

    @staticmethod
    def _make_db() -> AsyncMock:
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.flush = AsyncMock()
        db.rollback = AsyncMock()
        db.scalar = AsyncMock(return_value=0)
        return db

    @pytest.mark.asyncio
    async def test_discover_uses_inner_job_when_provided(self):
        from app.models.app_tables import ScrapeJob

        mp = _make_marketplace(sitemap_resume_offset=0)
        parent_id = uuid4()
        pending_job = ScrapeJob(
            job_type="discovery",
            marketplace_id=mp.id,
            parent_job_id=parent_id,
            status="pending",
        )
        urls = [f"https://shop.example/p/item-{i}" for i in range(10)]
        db = self._make_db()
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
            return_value=(10, 10, False),
        ):
            await crawler.discover(mp, inner_job=pending_job)

        new_scrape_jobs = [
            call.args[0]
            for call in db.add.call_args_list
            if isinstance(call.args[0], disc.ScrapeJob)
        ]
        assert new_scrape_jobs == [], (
            "discover() must NOT insert a new ScrapeJob when inner_job is provided"
        )
        assert pending_job.status in {"completed", "partial", "failed"}, (
            f"job did not finalize; status={pending_job.status}"
        )
        assert pending_job.parent_job_id == parent_id

    @pytest.mark.asyncio
    async def test_discover_creates_own_job_when_inner_job_none(self):
        mp = _make_marketplace(sitemap_resume_offset=0)
        urls = [f"https://shop.example/p/item-{i}" for i in range(10)]
        db = self._make_db()
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
            return_value=(10, 10, False),
        ):
            await crawler.discover(mp)

        new_scrape_jobs = [
            call.args[0]
            for call in db.add.call_args_list
            if isinstance(call.args[0], disc.ScrapeJob)
        ]
        assert len(new_scrape_jobs) == 1
