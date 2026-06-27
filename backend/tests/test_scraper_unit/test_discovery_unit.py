"""Unit tests for discovery helpers (pure functions + dataclass)."""

import asyncio
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

import app.modules.discovery.constants as disc_constants
import app.modules.discovery.orchestrator as disc
from app.modules.discovery import bfs_walker, category_processor
from app.modules.discovery.gate_persist import PoolWriteResult, write_pool_dtos_sync
from app.models.dimensions import DimMarketplace


@contextmanager
def _patch_discover_meta_writes():
    """Keep discover() unit tests DB-free (META door writes stubbed)."""
    ok = MagicMock(ok=True)
    mock_write = AsyncMock(return_value=ok)
    with (
        patch(
            "app.modules.discovery.orchestrator.write_meta_async",
            mock_write,
        ),
        patch(
            "app.modules.discovery.orchestrator._meta_update_marketplace_snapshot",
            new_callable=AsyncMock,
        ),
    ):
        yield mock_write


def _patch_pool_write(monkeypatch, *, slow_seconds: float | None = None) -> dict:
    """Capture pool DTO batches handed to asyncio.to_thread (gate write bridge)."""
    state: dict = {"batches": [], "calls": 0}

    async def fake_to_thread(func, dtos):
        state["calls"] += 1
        if slow_seconds:
            await asyncio.sleep(slow_seconds)
        state["batches"].append(list(dtos))
        assert func is write_pool_dtos_sync
        return PoolWriteResult(inserted=len(dtos), rejected=0)

    monkeypatch.setattr(asyncio, "to_thread", fake_to_thread)
    return state


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
async def test_save_product_urls_creates_new_rows(monkeypatch):
    """_save_product_urls hands new URLs to the gated pool write bridge."""
    mp_id = uuid4()
    db = AsyncMock()
    existing = MagicMock()
    existing.all.return_value = []
    db.execute = AsyncMock(return_value=existing)
    db.add = MagicMock()
    db.commit = AsyncMock()
    pool_state = _patch_pool_write(monkeypatch)

    crawler = disc.DiscoveryOrchestrator(db, MagicMock())
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
    assert pool_state["calls"] == 1
    assert len(pool_state["batches"][0]) == 2
    db.add.assert_not_called()
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_save_product_urls_skips_duplicate_hash(monkeypatch):
    mp_id = uuid4()
    url = "https://shop.example/p/exists"
    url_hash = disc.FactListing.compute_url_hash(url)
    db = AsyncMock()
    existing = MagicMock()
    existing.all.return_value = [(url_hash,)]
    db.execute = AsyncMock(return_value=existing)
    db.add = MagicMock()
    db.commit = AsyncMock()
    pool_state = _patch_pool_write(monkeypatch)

    crawler = disc.DiscoveryOrchestrator(db, MagicMock())
    new_count, next_offset, exhausted = await crawler._save_product_urls(mp_id, [url])
    assert new_count == 0
    assert next_offset == 1
    assert exhausted is False
    assert pool_state["calls"] == 0
    db.add.assert_not_called()


@pytest.mark.asyncio
async def test_filter_urls_by_role_empty():
    from unittest.mock import MagicMock

    crawler = disc.DiscoveryOrchestrator(MagicMock(), MagicMock())
    accepted, stats = await crawler._filter_urls_by_role([], requires_js=False, scrape_tier=1)
    assert accepted == []
    assert stats["mode"] == "empty"


@pytest.mark.asyncio
async def test_filter_urls_by_role_full_mode():
    from unittest.mock import AsyncMock, MagicMock

    crawler = disc.DiscoveryOrchestrator(MagicMock(), MagicMock())
    roles = {
        "https://shop.example/p/1": ("product", "https://shop.example/p/1", False),
        "https://shop.example/p/2": ("listing", "https://shop.example/p/2", False),
        "https://shop.example/p/3": ("product", "https://shop.example/p/3", False),
    }

    async def classify_side_effect(url: str, **kwargs):
        return roles[url]

    crawler._classify_and_resolve_url = AsyncMock(side_effect=classify_side_effect)

    accepted, stats = await crawler._filter_urls_by_role(
        list(roles), requires_js=False, scrape_tier=1, marketplace_locale=None,
    )
    assert stats["mode"] == "full"
    assert len(accepted) == 2
    assert stats["accepted"] == 2


@pytest.mark.asyncio
async def test_filter_urls_by_role_large_list_classifies_all(monkeypatch):
    from unittest.mock import AsyncMock, MagicMock

    crawler = disc.DiscoveryOrchestrator(MagicMock(), MagicMock())
    urls = [f"https://shop.example/p/{index}" for index in range(150)]
    crawler._classify_and_resolve_url = AsyncMock(
        return_value=("product", "https://shop.example/p/x", False),
    )
    monkeypatch.setattr(disc.random, "sample", lambda population, k: population[:k])

    accepted, stats = await crawler._filter_urls_by_role(
        urls, requires_js=False, scrape_tier=1, marketplace_locale=None,
    )
    assert stats["mode"] == "full_large"
    assert crawler._classify_and_resolve_url.await_count == 150
    assert len(accepted) == 1


@pytest.mark.asyncio
async def test_filter_urls_by_role_reject_sample(monkeypatch):
    from unittest.mock import AsyncMock, MagicMock

    crawler = disc.DiscoveryOrchestrator(MagicMock(), MagicMock())
    urls = [f"https://shop.example/page/{index}" for index in range(150)]
    call_count = 0

    async def classify_side_effect(url: str, **kwargs):
        nonlocal call_count
        call_count += 1
        role = "product" if call_count == 3 else "hub"
        return role, url, False

    crawler._classify_and_resolve_url = AsyncMock(side_effect=classify_side_effect)
    monkeypatch.setattr(disc.random, "sample", lambda population, k: population[:k])

    accepted, stats = await crawler._filter_urls_by_role(
        urls, requires_js=False, scrape_tier=1, marketplace_locale=None,
    )
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
    async def test_save_product_urls_respects_deadline(self, monkeypatch):
        mp_id = uuid4()
        db = _make_mock_db_for_save()
        pool_state = _patch_pool_write(monkeypatch, slow_seconds=0.3)
        urls = [f"https://shop.example/p/item-{i}" for i in range(1500)]

        crawler = disc.DiscoveryOrchestrator(db, MagicMock())
        deadline = time.monotonic() + 0.5
        new_count, next_offset, exhausted = await crawler._save_product_urls(
            mp_id, urls, deadline_monotonic=deadline,
        )

        # Deadline is checked once per batch (SAVE_PRODUCT_URLS_BATCH_SIZE
        # URLs == 500), AFTER each gated batch write. With a 0.5s budget and
        # 0.3s/batch, two batches commit (t=0.3 < 0.5 → continue; t=0.6 >= 0.5
        # → stop), so the resume offset lands at 2 batches.
        assert exhausted is True
        assert next_offset == 2 * disc_constants.SAVE_PRODUCT_URLS_BATCH_SIZE
        assert new_count == 2 * disc_constants.SAVE_PRODUCT_URLS_BATCH_SIZE
        assert pool_state["calls"] >= 2
        db.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_save_product_urls_resumes_from_offset(self, monkeypatch):
        mp_id = uuid4()
        db = _make_mock_db_for_save()
        pool_state = _patch_pool_write(monkeypatch)
        urls = [f"https://shop.example/p/item-{i}" for i in range(1000)]

        crawler = disc.DiscoveryOrchestrator(db, MagicMock())
        new_count, next_offset, exhausted = await crawler._save_product_urls(
            mp_id, urls, start_offset=500,
        )

        assert new_count == 500
        assert next_offset == 1000
        assert exhausted is False
        assert sum(len(batch) for batch in pool_state["batches"]) == 500

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

        crawler = disc.DiscoveryOrchestrator(db, MagicMock())

        with _patch_discover_meta_writes(), patch(
            "app.modules.discovery.sitemap_harvester.harvest_sitemap",
            new_callable=AsyncMock,
            return_value=urls,
        ), patch.object(
            disc.DiscoveryOrchestrator,
            "_save_product_urls",
            new_callable=AsyncMock,
            return_value=(300, 800, True),
        ):
            deadline = time.monotonic() + 60
            result = await crawler.discover(mp, deadline_monotonic=deadline)

        assert mp.sitemap_resume_offset == 800
        assert result.status == "partial_budget"

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

        crawler = disc.DiscoveryOrchestrator(db, MagicMock())

        with _patch_discover_meta_writes(), patch(
            "app.modules.discovery.sitemap_harvester.harvest_sitemap",
            new_callable=AsyncMock,
            return_value=urls,
        ), patch.object(
            disc.DiscoveryOrchestrator,
            "_save_product_urls",
            new_callable=AsyncMock,
            return_value=(200, 200, False),
        ):
            result = await crawler.discover(mp)

        assert mp.sitemap_resume_offset == 0
        assert result.status == "completed"

    def test_should_run_sitemap_harvest_with_offset(self):
        crawler = disc.DiscoveryOrchestrator(MagicMock(), MagicMock())
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
    """Cooperative deadline enforcement inside category_processor."""

    @staticmethod
    async def _run_phase2(crawler, mp, pool, db, urls, **kwargs):
        return await category_processor.run_product_harvest(
            mp,
            pool,
            db,
            urls,
            filter_urls_by_role=crawler._filter_urls_by_role,
            save_product_urls=crawler._save_product_urls,
            **kwargs,
        )

    def test_headroom_deadline_arithmetic(self):
        assert disc.DiscoveryOrchestrator._headroom_deadline(None) is None
        with patch("app.modules.discovery.orchestrator.time.monotonic", return_value=1000.0):
            result = disc.DiscoveryOrchestrator._headroom_deadline(1100.0)
        assert result == 1000.0 + 100.0 * disc_constants.SAVE_BUDGET_HEADROOM_FRACTION

    @pytest.mark.asyncio
    async def test_phase2_bails_before_fetch_when_deadline_expired(self):
        mp = _make_marketplace()
        pool = MagicMock()
        pool.scrape_page_for_analysis = AsyncMock()
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()

        crawler = disc.DiscoveryOrchestrator(db, pool)

        with patch(
            "app.modules.discovery.category_processor.time.monotonic",
            return_value=5000.0,
        ):
            urls = [f"https://shop.example/c/{i}" for i in range(10)]
            total, next_index, more = await self._run_phase2(
                crawler, mp, pool, db, urls, deadline_monotonic=4999.0,
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

        crawler = disc.DiscoveryOrchestrator(db, pool)

        clock = {"t": 0.0}

        def fake_monotonic():
            clock["t"] += 5.0
            return clock["t"]

        with patch(
            "app.modules.discovery.category_processor.time.monotonic",
            side_effect=fake_monotonic,
        ), patch(
            "app.modules.scraper.extractors.extract_links_from_repeated_structure",
            return_value=["https://shop.example/p/1"],
        ), patch(
            "app.modules.scraper.extractors.detect_next_page",
            return_value=None,
        ), patch.object(
            disc.DiscoveryOrchestrator,
            "_save_product_urls",
            new_callable=AsyncMock,
            return_value=(1, 1, False),
        ):
            urls = [f"https://shop.example/c/{i}" for i in range(5)]
            total, next_index, more = await self._run_phase2(
                crawler, mp, pool, db, urls, deadline_monotonic=20.0,
            )

        assert more is True
        assert 0 <= next_index < 5
        assert pool.scrape_page_for_analysis.await_count < 5

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

        crawler = disc.DiscoveryOrchestrator(db, MagicMock())

        with _patch_discover_meta_writes(), patch(
            "app.modules.discovery.sitemap_harvester.harvest_sitemap",
            new_callable=AsyncMock,
            return_value=[],
        ), patch.object(
            disc.DiscoveryOrchestrator,
            "_should_run_category_recon",
            return_value=False,
        ), patch(
            "app.modules.discovery.category_processor.run_product_harvest",
            new_callable=AsyncMock,
            return_value=(7, 2, True),
        ):
            result = await crawler.discover(mp, deadline_monotonic=time.monotonic() + 60)

        assert result.status == "partial_budget"
        assert mp.category_resume_index == 2

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

        crawler = disc.DiscoveryOrchestrator(db, MagicMock())
        captured: dict = {}

        async def capture_save(_mp_id, _batch, *, start_offset=0, deadline_monotonic=None):
            captured["deadline_monotonic"] = deadline_monotonic
            return (20, 20, False)

        with _patch_discover_meta_writes(), patch(
            "app.modules.discovery.sitemap_harvester.harvest_sitemap",
            new_callable=AsyncMock,
            return_value=urls,
        ), patch.object(
            disc.DiscoveryOrchestrator,
            "_save_product_urls",
            side_effect=capture_save,
        ), patch(
            "app.modules.discovery.orchestrator.time.monotonic",
            return_value=1000.0,
        ):
            await crawler.discover(mp, deadline_monotonic=1100.0)

        expected = 1000.0 + 100.0 * disc_constants.SAVE_BUDGET_HEADROOM_FRACTION
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

        crawler = disc.DiscoveryOrchestrator(db, pool)

        with patch(
            "app.modules.discovery.bfs_walker.time.monotonic",
            return_value=5000.0,
        ):
            urls, exhausted = await bfs_walker.run_category_bfs(
                mp, pool, db, deadline_monotonic=4000.0,
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

        crawler = disc.DiscoveryOrchestrator(db, pool)

        import logging as _logging
        with caplog.at_level(_logging.INFO, logger="app.modules.discovery.bfs_walker"):
            urls, exhausted = await bfs_walker.run_category_bfs(
                mp, pool, db, deadline_monotonic=None,
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

        crawler = disc.DiscoveryOrchestrator(db, pool)
        urls, exhausted = await bfs_walker.run_category_bfs(
            mp, pool, db, deadline_monotonic=None,
        )

        assert exhausted is False
        assert mp.recon_frontier_state is None
        assert mp.discovered_category_urls == urls

    def test_should_run_category_recon_with_frontier(self):
        crawler = disc.DiscoveryOrchestrator(MagicMock(), MagicMock())
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
    async def test_discover_skips_phase2_when_phase1_exhausted_no_backlog(self):
        mp = _make_marketplace(discovered_category_urls=[], category_resume_index=0)
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.flush = AsyncMock()
        db.rollback = AsyncMock()
        db.scalar = AsyncMock(return_value=0)

        crawler = disc.DiscoveryOrchestrator(db, MagicMock())

        with _patch_discover_meta_writes(), patch(
            "app.modules.discovery.sitemap_harvester.harvest_sitemap",
            new_callable=AsyncMock,
            return_value=[],
        ), patch.object(
            disc.DiscoveryOrchestrator,
            "_should_run_category_recon",
            return_value=True,
        ), patch(
            "app.modules.discovery.bfs_walker.run_category_bfs",
            new_callable=AsyncMock,
            return_value=(["u"], True),
        ), patch(
            "app.modules.discovery.category_processor.run_product_harvest",
            new_callable=AsyncMock,
        ) as phase2_mock:
            result = await crawler.discover(
                mp, deadline_monotonic=time.monotonic() + 60,
            )

        phase2_mock.assert_not_awaited()
        assert result.status == "partial_budget"

    @pytest.mark.asyncio
    async def test_discover_runs_phase2_when_phase1_exhausted_with_backlog(self):
        mp = _make_marketplace(
            discovered_category_urls=["https://x/c1"],
            category_resume_index=0,
        )
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.flush = AsyncMock()
        db.rollback = AsyncMock()
        db.scalar = AsyncMock(return_value=0)

        crawler = disc.DiscoveryOrchestrator(db, MagicMock())
        captured: dict = {"phase2_deadline": None}

        async def fake_phase2(
            marketplace,
            pool,
            db,
            category_urls,
            *,
            start_index=0,
            deadline_monotonic=None,
            on_activity=None,
            filter_urls_by_role=None,
            save_product_urls=None,
        ):
            captured["phase2_deadline"] = deadline_monotonic
            return (2, 0, False)

        with _patch_discover_meta_writes(), patch(
            "app.modules.discovery.sitemap_harvester.harvest_sitemap",
            new_callable=AsyncMock,
            return_value=[],
        ), patch.object(
            disc.DiscoveryOrchestrator,
            "_should_run_category_recon",
            return_value=True,
        ), patch(
            "app.modules.discovery.bfs_walker.run_category_bfs",
            new_callable=AsyncMock,
            return_value=([], True),
        ), patch(
            "app.modules.discovery.category_processor.run_product_harvest",
            side_effect=fake_phase2,
        ) as phase2_mock:
            result = await crawler.discover(
                mp, deadline_monotonic=time.monotonic() + 60,
            )

        phase2_mock.assert_awaited_once()
        assert captured["phase2_deadline"] is not None
        assert result.status == "completed"
        assert result.persisted_listings == 2

    @pytest.mark.asyncio
    async def test_resolve_category_backlog_divergence_writes_alert(self):
        mp = _make_marketplace(
            discovered_category_urls=["https://x/c1"],
            category_resume_index=1,
        )
        crawler = disc.DiscoveryOrchestrator(AsyncMock(), MagicMock())

        with patch(
            "app.modules.discovery.orchestrator.emit_discovery_service_alert",
            new_callable=AsyncMock,
        ) as alert_mock:
            effective = await crawler._resolve_category_backlog(mp)

        assert effective is True
        alert_mock.assert_awaited_once()
        args, kwargs = alert_mock.await_args
        assert args[0] == "budget_governor"
        assert args[1] == "warning"
        assert args[2] == "resume_index_desync"
        assert kwargs["context"]["resume_index"] == 1
        assert kwargs["context"]["categories_len"] == 1
        assert kwargs["marketplace_id"] == mp.id

    @pytest.mark.asyncio
    async def test_resolve_category_backlog_resume_index_oob_emits_alert(self):
        mp = _make_marketplace(
            discovered_category_urls=["https://x/c1"],
            category_resume_index=5,
        )
        crawler = disc.DiscoveryOrchestrator(AsyncMock(), MagicMock())

        with patch(
            "app.modules.discovery.orchestrator.emit_discovery_service_alert",
            new_callable=AsyncMock,
        ) as alert_mock:
            effective = await crawler._resolve_category_backlog(mp)

        assert effective is True
        oob_calls = [
            c
            for c in alert_mock.await_args_list
            if len(c.args) >= 3 and c.args[2] == "resume_index_oob"
        ]
        assert len(oob_calls) == 1
        assert oob_calls[0].args[0] == "cursor_store"
        assert oob_calls[0].kwargs["context"]["resume_index"] == 5
        assert oob_calls[0].kwargs["context"]["categories_len"] == 1

    @pytest.mark.asyncio
    async def test_resolve_category_backlog_in_range_no_oob_alert(self):
        mp = _make_marketplace(
            discovered_category_urls=["https://x/c1", "https://x/c2"],
            category_resume_index=1,
        )
        crawler = disc.DiscoveryOrchestrator(AsyncMock(), MagicMock())

        with patch(
            "app.modules.discovery.orchestrator.emit_discovery_service_alert",
            new_callable=AsyncMock,
        ) as alert_mock:
            effective = await crawler._resolve_category_backlog(mp)

        assert effective is True
        oob_calls = [
            c
            for c in alert_mock.await_args_list
            if len(c.args) >= 3 and c.args[2] == "resume_index_oob"
        ]
        assert len(oob_calls) == 0

    @pytest.mark.asyncio
    async def test_resolve_category_backlog_agreement_no_alert(self):
        mp = _make_marketplace(
            discovered_category_urls=["https://x/c1", "https://x/c2"],
            category_resume_index=0,
        )
        crawler = disc.DiscoveryOrchestrator(AsyncMock(), MagicMock())

        with patch(
            "app.modules.discovery.orchestrator.emit_discovery_service_alert",
            new_callable=AsyncMock,
        ) as alert_mock:
            effective = await crawler._resolve_category_backlog(mp)

        assert effective is True
        alert_mock.assert_not_awaited()

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

        crawler = disc.DiscoveryOrchestrator(db, MagicMock())
        captured: dict = {"phase1": None, "phase2": None}

        async def fake_phase1(marketplace, pool, db, *, deadline_monotonic=None, on_activity=None):
            captured["phase1"] = deadline_monotonic
            marketplace.discovered_category_urls = ["https://x/c1", "https://x/c2"]
            return (["https://x/c1", "https://x/c2"], False)

        async def fake_phase2(
            marketplace,
            pool,
            db,
            category_urls,
            *,
            start_index=0,
            deadline_monotonic=None,
            on_activity=None,
            filter_urls_by_role=None,
            save_product_urls=None,
        ):
            captured["phase2"] = deadline_monotonic
            return (4, 0, False)

        with _patch_discover_meta_writes(), patch(
            "app.modules.discovery.sitemap_harvester.harvest_sitemap",
            new_callable=AsyncMock,
            return_value=[],
        ), patch.object(
            disc.DiscoveryOrchestrator,
            "_should_run_category_recon",
            return_value=True,
        ), patch(
            "app.modules.discovery.bfs_walker.run_category_bfs",
            side_effect=fake_phase1,
        ), patch(
            "app.modules.discovery.category_processor.run_product_harvest",
            side_effect=fake_phase2,
        ):
            result = await crawler.discover(
                mp, deadline_monotonic=time.monotonic() + 60,
            )

        assert captured["phase1"] is not None
        assert captured["phase2"] is not None
        assert result.status == "completed"
        assert mp.category_resume_index == 0


class TestPhase1BatchPublish:
    """Phase 1 publishes categories in batches so Phase 2 starts before BFS ends."""

    @pytest.mark.asyncio
    async def test_phase1_publishes_batch_at_threshold(self):
        batch = disc_constants.CATEGORY_PUBLISH_BATCH
        listing = [f"https://shop.example/c/{i}" for i in range(batch - 1)]
        mp = _make_marketplace(
            base_url="https://shop.example/",
            recon_frontier_state={
                "queue": [
                    ["https://shop.example/c/last", 1],
                    ["https://shop.example/c/next", 1],
                ],
                "visited": ["https://shop.example/"] + listing,
                "listing_urls": listing,
            },
        )
        pool = MagicMock()
        pool.scrape_page_for_analysis = AsyncMock(return_value=("<html></html>", MagicMock()))
        db = AsyncMock()
        db.flush = AsyncMock()

        crawler = disc.DiscoveryOrchestrator(db, pool)

        with patch(
            "app.modules.discovery.classifier_adapter.classify_page_role",
            return_value="listing",
        ), patch(
            "app.modules.scraper.extractors.extract_internal_links_all",
            return_value=[],
        ):
            urls, exhausted = await bfs_walker.run_category_bfs(
                mp, pool, db, deadline_monotonic=None,
            )

        assert exhausted is False
        assert len(urls) == batch
        assert mp.discovered_category_urls == urls
        assert mp.category_resume_index == 0
        assert mp.recon_frontier_state is not None
        assert mp.recon_frontier_state["listing_urls"] == []
        assert len(mp.recon_frontier_state["queue"]) == 1

    @pytest.mark.asyncio
    async def test_phase1_deadline_with_findings_publishes(self):
        listing = ["https://shop.example/c/1", "https://shop.example/c/2"]
        mp = _make_marketplace(
            base_url="https://shop.example/",
            recon_frontier_state={
                "queue": [["https://shop.example/c/pending", 1]],
                "visited": ["https://shop.example/"],
                "listing_urls": listing,
            },
        )
        pool = MagicMock()
        db = AsyncMock()
        db.flush = AsyncMock()
        crawler = disc.DiscoveryOrchestrator(db, pool)

        with patch(
            "app.modules.discovery.bfs_walker.time.monotonic",
            return_value=5000.0,
        ):
            urls, exhausted = await bfs_walker.run_category_bfs(
                mp, pool, db, deadline_monotonic=4000.0,
            )

        assert exhausted is False
        assert urls == listing
        assert mp.discovered_category_urls == listing
        assert mp.recon_frontier_state is not None
        assert mp.recon_frontier_state["listing_urls"] == []

    @pytest.mark.asyncio
    async def test_phase1_deadline_with_no_findings_preserves_frontier_exhausted(self):
        mp = _make_marketplace(recon_frontier_state=None)
        pool = MagicMock()
        pool.scrape_page_for_analysis = AsyncMock()
        db = AsyncMock()
        db.flush = AsyncMock()
        crawler = disc.DiscoveryOrchestrator(db, pool)

        with patch(
            "app.modules.discovery.bfs_walker.time.monotonic",
            return_value=5000.0,
        ):
            urls, exhausted = await bfs_walker.run_category_bfs(
                mp, pool, db, deadline_monotonic=4000.0,
            )

        assert (urls, exhausted) == ([], True)
        assert mp.discovered_category_urls == []
        assert isinstance(mp.recon_frontier_state, dict)
        assert mp.recon_frontier_state["listing_urls"] == []

    @pytest.mark.asyncio
    async def test_phase1_empty_queue_clean_completion(self):
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
        db.flush = AsyncMock()
        crawler = disc.DiscoveryOrchestrator(db, pool)

        urls, exhausted = await bfs_walker.run_category_bfs(
            mp, pool, db, deadline_monotonic=None,
        )

        assert exhausted is False
        assert mp.recon_frontier_state is None
        assert mp.discovered_category_urls == urls

    @pytest.mark.asyncio
    async def test_discover_runs_phase2_after_batch_publish(self):
        mp = _make_marketplace()
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.flush = AsyncMock()
        db.rollback = AsyncMock()
        db.scalar = AsyncMock(return_value=0)

        crawler = disc.DiscoveryOrchestrator(db, MagicMock())
        published = [f"https://x/c/{i}" for i in range(3)]

        async def fake_phase1(marketplace, pool, db, *, deadline_monotonic=None, on_activity=None):
            marketplace.discovered_category_urls = list(published)
            return (published, False)

        async def fake_phase2(
            marketplace,
            pool,
            db,
            category_urls,
            *,
            start_index=0,
            deadline_monotonic=None,
            on_activity=None,
            filter_urls_by_role=None,
            save_product_urls=None,
        ):
            assert category_urls == [marketplace.base_url] + published
            return (2, 0, False)

        with _patch_discover_meta_writes(), patch(
            "app.modules.discovery.sitemap_harvester.harvest_sitemap",
            new_callable=AsyncMock,
            return_value=[],
        ), patch.object(
            disc.DiscoveryOrchestrator,
            "_should_run_category_recon",
            return_value=True,
        ), patch(
            "app.modules.discovery.bfs_walker.run_category_bfs",
            side_effect=fake_phase1,
        ), patch(
            "app.modules.discovery.category_processor.run_product_harvest",
            side_effect=fake_phase2,
        ) as phase2_mock:
            result = await crawler.discover(
                mp, deadline_monotonic=time.monotonic() + 60,
            )

        phase2_mock.assert_awaited_once()
        assert result.status == "completed"


class TestPhase2CategoryResume:
    """Cursor state machine for resumable category harvest in category_processor."""

    @staticmethod
    async def _run_phase2(crawler, mp, pool, db, urls, **kwargs):
        return await category_processor.run_product_harvest(
            mp,
            pool,
            db,
            urls,
            filter_urls_by_role=crawler._filter_urls_by_role,
            save_product_urls=crawler._save_product_urls,
            **kwargs,
        )

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
        crawler = disc.DiscoveryOrchestrator(db, pool)
        return crawler, pool

    @pytest.mark.asyncio
    async def test_phase2_empty_window_when_list_shrank(self):
        mp = _make_marketplace()
        crawler, pool = self._setup_crawler_with_soup()
        urls = [f"https://shop.example/c/{i}" for i in range(3)]

        total, next_index, more = await self._run_phase2(
            crawler, mp, pool, crawler.db, urls, start_index=5,
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

        crawler = disc.DiscoveryOrchestrator(db, MagicMock())

        with _patch_discover_meta_writes(), patch(
            "app.modules.discovery.sitemap_harvester.harvest_sitemap",
            new_callable=AsyncMock,
            return_value=[],
        ), patch.object(
            disc.DiscoveryOrchestrator,
            "_should_run_category_recon",
            return_value=False,
        ), patch(
            "app.modules.discovery.category_processor.run_product_harvest",
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

        crawler = disc.DiscoveryOrchestrator(db, MagicMock())

        with _patch_discover_meta_writes(), patch(
            "app.modules.discovery.sitemap_harvester.harvest_sitemap",
            new_callable=AsyncMock,
            return_value=[],
        ), patch.object(
            disc.DiscoveryOrchestrator,
            "_should_run_category_recon",
            return_value=False,
        ), patch(
            "app.modules.discovery.category_processor.run_product_harvest",
            new_callable=AsyncMock,
            return_value=(5, 0, False),
        ):
            result = await crawler.discover(
                mp, deadline_monotonic=time.monotonic() + 60,
            )

        assert mp.category_resume_index == 0
        assert result.status == "completed"

    def test_should_run_category_recon_skipped_when_resume_index_set(self):
        crawler = disc.DiscoveryOrchestrator(MagicMock(), MagicMock())
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

        crawler = disc.DiscoveryOrchestrator(db, pool)
        urls, exhausted = await bfs_walker.run_category_bfs(
            mp, pool, db, deadline_monotonic=None,
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
        db.get = AsyncMock(return_value=MagicMock())
        return db

    @pytest.mark.asyncio
    async def test_discover_sets_parent_job_id_when_provided(self):
        mp = _make_marketplace(sitemap_resume_offset=0)
        urls = [f"https://shop.example/p/item-{i}" for i in range(10)]
        db = self._make_db()
        parent_id = uuid4()

        crawler = disc.DiscoveryOrchestrator(db, MagicMock())

        with _patch_discover_meta_writes() as meta_write, patch(
            "app.modules.discovery.sitemap_harvester.harvest_sitemap",
            new_callable=AsyncMock,
            return_value=urls,
        ), patch.object(
            disc.DiscoveryOrchestrator,
            "_save_product_urls",
            new_callable=AsyncMock,
            return_value=(10, 10, False),
        ):
            await crawler.discover(mp, parent_job_id=parent_id)

        insert_calls = [
            call
            for call in meta_write.await_args_list
            if call.kwargs.get("operation") == "insert"
            and call.kwargs.get("table") == "scrape_jobs"
        ]
        assert insert_calls, "expected scrape_jobs insert via write_meta_async"
        assert insert_calls[0].kwargs["fields"]["parent_job_id"] == str(parent_id)

    @pytest.mark.asyncio
    async def test_discover_parent_job_id_defaults_none(self):
        mp = _make_marketplace(sitemap_resume_offset=0)
        urls = [f"https://shop.example/p/item-{i}" for i in range(10)]
        db = self._make_db()

        crawler = disc.DiscoveryOrchestrator(db, MagicMock())

        with _patch_discover_meta_writes() as meta_write, patch(
            "app.modules.discovery.sitemap_harvester.harvest_sitemap",
            new_callable=AsyncMock,
            return_value=urls,
        ), patch.object(
            disc.DiscoveryOrchestrator,
            "_save_product_urls",
            new_callable=AsyncMock,
            return_value=(10, 10, False),
        ):
            await crawler.discover(mp)

        insert_calls = [
            call
            for call in meta_write.await_args_list
            if call.kwargs.get("operation") == "insert"
            and call.kwargs.get("table") == "scrape_jobs"
        ]
        assert insert_calls, "expected scrape_jobs insert via write_meta_async"
        assert insert_calls[0].kwargs["fields"]["parent_job_id"] is None

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
        db.get = AsyncMock(return_value=MagicMock())
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
        crawler = disc.DiscoveryOrchestrator(db, MagicMock())

        with _patch_discover_meta_writes() as meta_write, patch(
            "app.modules.discovery.sitemap_harvester.harvest_sitemap",
            new_callable=AsyncMock,
            return_value=urls,
        ), patch.object(
            disc.DiscoveryOrchestrator,
            "_save_product_urls",
            new_callable=AsyncMock,
            return_value=(10, 10, False),
        ):
            await crawler.discover(mp, inner_job=pending_job)

        insert_calls = [
            call
            for call in meta_write.await_args_list
            if call.kwargs.get("operation") == "insert"
            and call.kwargs.get("table") == "scrape_jobs"
        ]
        assert insert_calls == [], (
            "discover() must NOT insert a new ScrapeJob when inner_job is provided"
        )
        update_calls = [
            call
            for call in meta_write.await_args_list
            if call.kwargs.get("operation") == "update"
            and call.kwargs.get("table") == "scrape_jobs"
        ]
        assert update_calls, "expected inner job update via write_meta_async"
        assert pending_job.parent_job_id == parent_id

    @pytest.mark.asyncio
    async def test_discover_creates_own_job_when_inner_job_none(self):
        mp = _make_marketplace(sitemap_resume_offset=0)
        urls = [f"https://shop.example/p/item-{i}" for i in range(10)]
        db = self._make_db()
        crawler = disc.DiscoveryOrchestrator(db, MagicMock())

        with _patch_discover_meta_writes() as meta_write, patch(
            "app.modules.discovery.sitemap_harvester.harvest_sitemap",
            new_callable=AsyncMock,
            return_value=urls,
        ), patch.object(
            disc.DiscoveryOrchestrator,
            "_save_product_urls",
            new_callable=AsyncMock,
            return_value=(10, 10, False),
        ):
            await crawler.discover(mp)

        insert_calls = [
            call
            for call in meta_write.await_args_list
            if call.kwargs.get("operation") == "insert"
            and call.kwargs.get("table") == "scrape_jobs"
        ]
        assert len(insert_calls) == 1


class TestOrchestratorDefenceInDepth:
    """NODE 1: success META retry, discover_exception, status inconsistency alerts."""

    @staticmethod
    def _make_discover_db() -> AsyncMock:
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.flush = AsyncMock()
        db.rollback = AsyncMock()
        db.scalar = AsyncMock(return_value=0)
        db.get = AsyncMock(return_value=MagicMock(id=uuid4()))
        return db

    @pytest.mark.asyncio
    async def test_success_meta_snapshot_retries_once_then_succeeds(self):
        mp = _make_marketplace()
        job_id = uuid4()
        snapshot_mock = AsyncMock(side_effect=[RuntimeError("transient"), None])

        with (
            patch(
                "app.modules.discovery.orchestrator._meta_update_marketplace_snapshot",
                snapshot_mock,
            ),
            patch(
                "app.modules.discovery.orchestrator.emit_discovery_service_alert",
                new_callable=AsyncMock,
            ) as alert_mock,
        ):
            await disc._success_meta_snapshot_with_retry(
                mp,
                job_id=job_id,
                status="completed",
                persisted_listings=5,
            )

        assert snapshot_mock.await_count == 2
        alert_mock.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_success_meta_snapshot_double_fail_emits_critical_alert(self):
        mp = _make_marketplace()
        job_id = uuid4()

        with (
            patch(
                "app.modules.discovery.orchestrator._meta_update_marketplace_snapshot",
                new_callable=AsyncMock,
                side_effect=RuntimeError("persistent"),
            ),
            patch(
                "app.modules.discovery.orchestrator.emit_discovery_service_alert",
                new_callable=AsyncMock,
            ) as alert_mock,
        ):
            await disc._success_meta_snapshot_with_retry(
                mp,
                job_id=job_id,
                status="completed",
                persisted_listings=3,
            )

        alert_mock.assert_awaited_once()
        args = alert_mock.await_args.args
        assert args[0] == "orchestrator"
        assert args[1] == "critical"
        assert args[2] == "meta_snapshot_write_failed"
        assert alert_mock.await_args.kwargs["context"]["write_target"] == "dim_marketplace"
        assert alert_mock.await_args.kwargs["context"]["job_id"] == str(job_id)

    @pytest.mark.asyncio
    async def test_discover_meta_snapshot_double_fail_still_returns_success(self):
        mp = _make_marketplace()
        urls = [f"https://shop.example/p/item-{i}" for i in range(200)]
        db = self._make_discover_db()

        crawler = disc.DiscoveryOrchestrator(db, MagicMock())
        ok = MagicMock(ok=True)

        with (
            patch(
                "app.modules.discovery.orchestrator.write_meta_async",
                new_callable=AsyncMock,
                return_value=ok,
            ),
            patch(
                "app.modules.discovery.orchestrator._meta_update_marketplace_snapshot",
                new_callable=AsyncMock,
                side_effect=RuntimeError("persistent"),
            ),
            patch(
                "app.modules.discovery.orchestrator.emit_discovery_service_alert",
                new_callable=AsyncMock,
            ) as alert_mock,
            patch(
                "app.modules.discovery.sitemap_harvester.harvest_sitemap",
                new_callable=AsyncMock,
                return_value=urls,
            ),
            patch.object(
                disc.DiscoveryOrchestrator,
                "_save_product_urls",
                new_callable=AsyncMock,
                return_value=(200, 200, False),
            ),
        ):
            result = await crawler.discover(mp)

        assert result.status == "completed"
        assert result.persisted_listings == 200
        critical_calls = [
            c
            for c in alert_mock.await_args_list
            if len(c.args) >= 3 and c.args[2] == "meta_snapshot_write_failed"
        ]
        assert len(critical_calls) == 1

    @pytest.mark.asyncio
    async def test_discover_exception_emits_alert_and_preserves_error_flow(self):
        mp = _make_marketplace()
        db = self._make_discover_db()
        crawler = disc.DiscoveryOrchestrator(db, MagicMock())
        ok = MagicMock(ok=True)
        meta_write = AsyncMock(return_value=ok)

        with (
            patch(
                "app.modules.discovery.orchestrator.write_meta_async",
                meta_write,
            ),
            patch(
                "app.modules.discovery.orchestrator._meta_update_marketplace_snapshot",
                new_callable=AsyncMock,
            ),
            patch(
                "app.modules.discovery.orchestrator.emit_discovery_service_alert",
                new_callable=AsyncMock,
            ) as alert_mock,
            patch.object(
                disc.DiscoveryOrchestrator,
                "_should_run_sitemap_harvest",
                return_value=True,
            ),
            patch(
                "app.modules.discovery.sitemap_harvester.harvest_sitemap",
                new_callable=AsyncMock,
                side_effect=RuntimeError("phase boom"),
            ),
        ):
            result = await crawler.discover(mp)

        assert result.status == "error"
        assert any("phase boom" in e for e in result.errors)
        exception_calls = [
            c
            for c in alert_mock.await_args_list
            if len(c.args) >= 3 and c.args[2] == "discover_exception"
        ]
        assert len(exception_calls) == 1
        ctx = exception_calls[0].kwargs["context"]
        assert ctx["status"] == "error"
        assert ctx["exc_type"] == "RuntimeError"
        assert ctx["phase"] == "sitemap_harvest"
        job_updates = [
            c
            for c in meta_write.await_args_list
            if c.kwargs.get("operation") == "update"
            and c.kwargs.get("table") == "scrape_jobs"
        ]
        assert any(
            c.kwargs["fields"].get("status") == "failed" for c in job_updates
        )

    @pytest.mark.asyncio
    async def test_discover_status_inconsistent_emits_warning(self):
        mp_id = uuid4()
        with patch(
            "app.modules.discovery.orchestrator.emit_discovery_service_alert",
            new_callable=AsyncMock,
        ) as alert_mock:
            await disc._emit_discover_status_inconsistent_if_needed(
                marketplace_id=mp_id,
                status="no_categories",
                persisted_listings=5,
                candidate_urls_found=0,
                accepted_urls=0,
            )

        alert_mock.assert_awaited_once()
        args = alert_mock.await_args.args
        assert args[0] == "orchestrator"
        assert args[1] == "warning"
        assert args[2] == "discover_status_inconsistent"
        assert alert_mock.await_args.kwargs["context"]["persisted_listings"] == 5

    @pytest.mark.asyncio
    async def test_discover_status_inconsistent_no_false_positive(self):
        mp_id = uuid4()
        with patch(
            "app.modules.discovery.orchestrator.emit_discovery_service_alert",
            new_callable=AsyncMock,
        ) as alert_mock:
            await disc._emit_discover_status_inconsistent_if_needed(
                marketplace_id=mp_id,
                status="no_categories",
                persisted_listings=0,
                candidate_urls_found=0,
                accepted_urls=0,
            )

        alert_mock.assert_not_awaited()


class TestGatePersistDefenceInDepth:
    """NODE 2: gate_persist anomalies detected in _save_product_urls."""

    @pytest.mark.asyncio
    async def test_pool_batch_total_reject_emits_warning(self, monkeypatch):
        mp_id = uuid4()
        db = _make_mock_db_for_save()

        async def fake_to_thread(func, dtos):
            assert func is write_pool_dtos_sync
            return PoolWriteResult(inserted=0, rejected=len(dtos))

        monkeypatch.setattr(asyncio, "to_thread", fake_to_thread)

        with patch(
            "app.modules.discovery.orchestrator.emit_discovery_service_alert",
            new_callable=AsyncMock,
        ) as alert_mock:
            crawler = disc.DiscoveryOrchestrator(db, MagicMock())
            new_count, next_offset, exhausted = await crawler._save_product_urls(
                mp_id,
                [
                    "https://shop.example/p/a",
                    "https://shop.example/p/b",
                ],
            )

        assert new_count == 0
        assert next_offset == 2
        assert exhausted is False
        alert_mock.assert_awaited_once()
        args = alert_mock.await_args.args
        assert args[0] == "gate_persist"
        assert args[1] == "warning"
        assert args[2] == "pool_batch_total_reject"
        assert alert_mock.await_args.kwargs["context"]["batch_size"] == 2
        assert alert_mock.await_args.kwargs["context"]["inserted"] == 0
        assert alert_mock.await_args.kwargs["context"]["rejected"] == 2

    @pytest.mark.asyncio
    async def test_pool_batch_partial_reject_no_alert(self, monkeypatch):
        mp_id = uuid4()
        db = _make_mock_db_for_save()

        async def fake_to_thread(func, dtos):
            return PoolWriteResult(inserted=1, rejected=1)

        monkeypatch.setattr(asyncio, "to_thread", fake_to_thread)

        with patch(
            "app.modules.discovery.orchestrator.emit_discovery_service_alert",
            new_callable=AsyncMock,
        ) as alert_mock:
            crawler = disc.DiscoveryOrchestrator(db, MagicMock())
            new_count, next_offset, exhausted = await crawler._save_product_urls(
                mp_id,
                [
                    "https://shop.example/p/a",
                    "https://shop.example/p/b",
                ],
            )

        assert new_count == 1
        assert next_offset == 2
        assert exhausted is False
        alert_mock.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_pool_batch_empty_batch_no_alert(self, monkeypatch):
        mp_id = uuid4()
        url = "https://shop.example/p/exists"
        url_hash = disc.FactListing.compute_url_hash(url)
        db = _make_mock_db_for_save(existing_hashes=[url_hash])
        pool_state = _patch_pool_write(monkeypatch)

        with patch(
            "app.modules.discovery.orchestrator.emit_discovery_service_alert",
            new_callable=AsyncMock,
        ) as alert_mock:
            crawler = disc.DiscoveryOrchestrator(db, MagicMock())
            new_count, next_offset, exhausted = await crawler._save_product_urls(
                mp_id, [url],
            )

        assert new_count == 0
        assert pool_state["calls"] == 0
        alert_mock.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_pool_batch_commit_failed_emits_alert_and_reraises(
        self, monkeypatch,
    ):
        mp_id = uuid4()
        db = _make_mock_db_for_save()

        async def fake_to_thread(func, dtos):
            raise RuntimeError("commit failed")

        monkeypatch.setattr(asyncio, "to_thread", fake_to_thread)

        with (
            patch(
                "app.modules.discovery.orchestrator.emit_discovery_service_alert",
                new_callable=AsyncMock,
            ) as alert_mock,
            pytest.raises(RuntimeError, match="commit failed"),
        ):
            crawler = disc.DiscoveryOrchestrator(db, MagicMock())
            await crawler._save_product_urls(
                mp_id,
                ["https://shop.example/p/a"],
            )

        alert_mock.assert_awaited_once()
        args = alert_mock.await_args.args
        assert args[0] == "gate_persist"
        assert args[1] == "error"
        assert args[2] == "pool_batch_commit_failed"
        assert alert_mock.await_args.kwargs["context"]["exc_type"] == "RuntimeError"

    @pytest.mark.asyncio
    async def test_pool_batch_success_no_alert(self, monkeypatch):
        mp_id = uuid4()
        db = _make_mock_db_for_save()
        pool_state = _patch_pool_write(monkeypatch)

        with patch(
            "app.modules.discovery.orchestrator.emit_discovery_service_alert",
            new_callable=AsyncMock,
        ) as alert_mock:
            crawler = disc.DiscoveryOrchestrator(db, MagicMock())
            new_count, next_offset, exhausted = await crawler._save_product_urls(
                mp_id,
                [
                    "https://unique-shop.example/p/one",
                    "https://unique-shop.example/p/two",
                ],
            )

        assert new_count == 2
        assert next_offset == 2
        assert exhausted is False
        assert pool_state["calls"] == 1
        alert_mock.assert_not_awaited()


class TestUrlCanonicalizerDefenceInDepth:
    """NODE 8: dedup lookup degrade + canonical missing rate alerts."""

    @pytest.mark.asyncio
    async def test_dedup_lookup_failed_emits_alert_and_continues(self, monkeypatch):
        mp_id = uuid4()
        db = _make_mock_db_for_save()
        db.execute = AsyncMock(side_effect=RuntimeError("db down"))
        pool_state = _patch_pool_write(monkeypatch)

        with patch(
            "app.modules.discovery.orchestrator.emit_discovery_service_alert",
            new_callable=AsyncMock,
        ) as alert_mock:
            crawler = disc.DiscoveryOrchestrator(db, MagicMock())
            new_count, next_offset, exhausted = await crawler._save_product_urls(
                mp_id,
                [
                    "https://shop.example/p/a",
                    "https://shop.example/p/b",
                ],
            )

        assert new_count == 2
        assert next_offset == 2
        assert exhausted is False
        assert pool_state["calls"] == 1
        alert_mock.assert_awaited_once()
        args = alert_mock.await_args.args
        assert args[0] == "url_canonicalizer"
        assert args[1] == "error"
        assert args[2] == "dedup_lookup_failed"
        assert alert_mock.await_args.kwargs["context"]["hash_count"] == 2
        assert alert_mock.await_args.kwargs["context"]["exc_type"] == "RuntimeError"

    @pytest.mark.asyncio
    async def test_dedup_lookup_success_no_alert(self, monkeypatch):
        mp_id = uuid4()
        db = _make_mock_db_for_save()
        pool_state = _patch_pool_write(monkeypatch)

        with patch(
            "app.modules.discovery.orchestrator.emit_discovery_service_alert",
            new_callable=AsyncMock,
        ) as alert_mock:
            crawler = disc.DiscoveryOrchestrator(db, MagicMock())
            new_count, next_offset, exhausted = await crawler._save_product_urls(
                mp_id,
                ["https://shop.example/p/new"],
            )

        assert new_count == 1
        assert pool_state["calls"] == 1
        alert_mock.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_canonical_missing_rate_high_emits_info(self) -> None:
        mp_id = uuid4()
        crawler = disc.DiscoveryOrchestrator(MagicMock(), MagicMock())
        urls = [f"https://shop.example/p/{index}" for index in range(10)]

        async def classify_side_effect(url: str, **kwargs):
            return "product", url, True

        crawler._classify_and_resolve_url = AsyncMock(side_effect=classify_side_effect)

        with patch(
            "app.modules.discovery.alerting.emit_discovery_service_alert",
            new_callable=AsyncMock,
        ) as alert_mock:
            await crawler._filter_urls_by_role(
                urls,
                requires_js=False,
                scrape_tier=1,
                marketplace_id=mp_id,
            )

        rate_calls = [
            c
            for c in alert_mock.await_args_list
            if len(c.args) >= 3 and c.args[2] == "canonical_missing_rate_high"
        ]
        assert len(rate_calls) == 1
        assert rate_calls[0].args[0] == "url_canonicalizer"
        assert rate_calls[0].args[1] == "info"
        ctx = rate_calls[0].kwargs["context"]
        assert ctx["classified"] == 10
        assert ctx["canonical_missing"] == 10
        assert ctx["rate"] == 1.0

    @pytest.mark.asyncio
    async def test_canonical_missing_rate_at_threshold_emits_info(self) -> None:
        mp_id = uuid4()
        crawler = disc.DiscoveryOrchestrator(MagicMock(), MagicMock())
        urls = [f"https://shop.example/p/{index}" for index in range(10)]

        async def classify_side_effect(url: str, **kwargs):
            if url.endswith("/p/0"):
                return "product", url, False
            return "product", url, True

        crawler._classify_and_resolve_url = AsyncMock(side_effect=classify_side_effect)

        with patch(
            "app.modules.discovery.alerting.emit_discovery_service_alert",
            new_callable=AsyncMock,
        ) as alert_mock:
            await crawler._filter_urls_by_role(
                urls,
                requires_js=False,
                scrape_tier=1,
                marketplace_id=mp_id,
            )

        rate_calls = [
            c
            for c in alert_mock.await_args_list
            if len(c.args) >= 3 and c.args[2] == "canonical_missing_rate_high"
        ]
        assert len(rate_calls) == 1
        assert rate_calls[0].kwargs["context"]["rate"] == 0.9

    @pytest.mark.asyncio
    async def test_canonical_missing_rate_below_threshold_no_alert(self) -> None:
        mp_id = uuid4()
        crawler = disc.DiscoveryOrchestrator(MagicMock(), MagicMock())
        urls = [f"https://shop.example/p/{index}" for index in range(10)]

        async def classify_side_effect(url: str, **kwargs):
            if url.endswith("/p/0") or url.endswith("/p/1"):
                return "product", url, False
            return "product", url, True

        crawler._classify_and_resolve_url = AsyncMock(side_effect=classify_side_effect)

        with patch(
            "app.modules.discovery.alerting.emit_discovery_service_alert",
            new_callable=AsyncMock,
        ) as alert_mock:
            await crawler._filter_urls_by_role(
                urls,
                requires_js=False,
                scrape_tier=1,
                marketplace_id=mp_id,
            )

        rate_calls = [
            c
            for c in alert_mock.await_args_list
            if len(c.args) >= 3 and c.args[2] == "canonical_missing_rate_high"
        ]
        assert len(rate_calls) == 0

    @pytest.mark.asyncio
    async def test_canonical_missing_below_min_classified_no_alert(self) -> None:
        mp_id = uuid4()
        crawler = disc.DiscoveryOrchestrator(MagicMock(), MagicMock())
        urls = [f"https://shop.example/p/{index}" for index in range(9)]

        crawler._classify_and_resolve_url = AsyncMock(
            return_value=("product", "https://shop.example/p/x", True),
        )

        with patch(
            "app.modules.discovery.alerting.emit_discovery_service_alert",
            new_callable=AsyncMock,
        ) as alert_mock:
            await crawler._filter_urls_by_role(
                urls,
                requires_js=False,
                scrape_tier=1,
                marketplace_id=mp_id,
            )

        rate_calls = [
            c
            for c in alert_mock.await_args_list
            if len(c.args) >= 3 and c.args[2] == "canonical_missing_rate_high"
        ]
        assert len(rate_calls) == 0

    @pytest.mark.asyncio
    async def test_canonical_present_on_most_pages_no_rate_alert(self) -> None:
        mp_id = uuid4()
        crawler = disc.DiscoveryOrchestrator(MagicMock(), MagicMock())
        urls = [f"https://shop.example/p/{index}" for index in range(10)]

        crawler._classify_and_resolve_url = AsyncMock(
            return_value=("product", "https://shop.example/p/x", False),
        )

        with patch(
            "app.modules.discovery.alerting.emit_discovery_service_alert",
            new_callable=AsyncMock,
        ) as alert_mock:
            await crawler._filter_urls_by_role(
                urls,
                requires_js=False,
                scrape_tier=1,
                marketplace_id=mp_id,
            )

        canonical_calls = [
            c
            for c in alert_mock.await_args_list
            if len(c.args) >= 3 and c.args[2] == "canonical_missing_rate_high"
        ]
        assert len(canonical_calls) == 0


class TestClassifierAdapterDefenceInDepth:
    """NODE 9: classify unknown rate spike alerts in gate aggregate."""

    @pytest.mark.asyncio
    async def test_classify_unknown_rate_high_emits_warning(self) -> None:
        mp_id = uuid4()
        crawler = disc.DiscoveryOrchestrator(MagicMock(), MagicMock())
        urls = [f"https://shop.example/p/{index}" for index in range(10)]

        async def classify_side_effect(url: str, **kwargs):
            if url.endswith("/p/0") or url.endswith("/p/1") or url.endswith("/p/2"):
                return "product", url, False
            return "unknown", url, False

        crawler._classify_and_resolve_url = AsyncMock(side_effect=classify_side_effect)

        with patch(
            "app.modules.discovery.alerting.emit_discovery_service_alert",
            new_callable=AsyncMock,
        ) as alert_mock:
            accepted, stats = await crawler._filter_urls_by_role(
                urls,
                requires_js=False,
                scrape_tier=1,
                marketplace_id=mp_id,
            )

        assert stats["mode"] == "full"
        assert len(accepted) == 3
        unknown_calls = [
            c
            for c in alert_mock.await_args_list
            if len(c.args) >= 3 and c.args[2] == "classify_unknown_rate_high"
        ]
        assert len(unknown_calls) == 1
        assert unknown_calls[0].args[0] == "classifier_adapter"
        assert unknown_calls[0].args[1] == "warning"
        ctx = unknown_calls[0].kwargs["context"]
        assert ctx["classified"] == 10
        assert ctx["unknown_count"] == 7
        assert ctx["rate"] == 0.7
        assert ctx["mode"] == "full"

    @pytest.mark.asyncio
    async def test_reject_sample_mode_skips_unknown_alert(self, monkeypatch) -> None:
        mp_id = uuid4()
        crawler = disc.DiscoveryOrchestrator(MagicMock(), MagicMock())
        urls = [f"https://shop.example/page/{index}" for index in range(150)]
        call_count = 0

        async def classify_side_effect(url: str, **kwargs):
            nonlocal call_count
            call_count += 1
            return "unknown", url, False

        crawler._classify_and_resolve_url = AsyncMock(side_effect=classify_side_effect)
        monkeypatch.setattr(disc.random, "sample", lambda population, k: population[:k])

        with patch(
            "app.modules.discovery.alerting.emit_discovery_service_alert",
            new_callable=AsyncMock,
        ) as alert_mock:
            _accepted, stats = await crawler._filter_urls_by_role(
                urls,
                requires_js=False,
                scrape_tier=1,
                marketplace_id=mp_id,
            )

        assert stats["mode"] == "reject_sample"
        unknown_calls = [
            c
            for c in alert_mock.await_args_list
            if len(c.args) >= 3 and c.args[2] == "classify_unknown_rate_high"
        ]
        assert len(unknown_calls) == 0

    @pytest.mark.asyncio
    async def test_classify_unknown_rate_below_threshold_no_alert(self) -> None:
        mp_id = uuid4()
        crawler = disc.DiscoveryOrchestrator(MagicMock(), MagicMock())
        urls = [f"https://shop.example/p/{index}" for index in range(10)]

        async def classify_side_effect(url: str, **kwargs):
            if url.endswith("/p/0") or url.endswith("/p/1") or url.endswith("/p/2"):
                return "product", url, False
            if url.endswith("/p/3"):
                return "unknown", url, False
            return "listing", url, False

        crawler._classify_and_resolve_url = AsyncMock(side_effect=classify_side_effect)

        with patch(
            "app.modules.discovery.alerting.emit_discovery_service_alert",
            new_callable=AsyncMock,
        ) as alert_mock:
            await crawler._filter_urls_by_role(
                urls,
                requires_js=False,
                scrape_tier=1,
                marketplace_id=mp_id,
            )

        unknown_calls = [
            c
            for c in alert_mock.await_args_list
            if len(c.args) >= 3 and c.args[2] == "classify_unknown_rate_high"
        ]
        assert len(unknown_calls) == 0

    @pytest.mark.asyncio
    async def test_fetch_failure_unknown_not_counted(self) -> None:
        mp_id = uuid4()
        crawler = disc.DiscoveryOrchestrator(MagicMock(), MagicMock())
        urls = [f"https://shop.example/p/{index}" for index in range(10)]

        async def classify_side_effect(url: str, **kwargs):
            if url.endswith("/p/0") or url.endswith("/p/1") or url.endswith("/p/2"):
                return "unknown", url, None
            if url.endswith("/p/3"):
                return "product", url, False
            return "unknown", url, False

        crawler._classify_and_resolve_url = AsyncMock(side_effect=classify_side_effect)

        with patch(
            "app.modules.discovery.alerting.emit_discovery_service_alert",
            new_callable=AsyncMock,
        ) as alert_mock:
            await crawler._filter_urls_by_role(
                urls,
                requires_js=False,
                scrape_tier=1,
                marketplace_id=mp_id,
            )

        unknown_calls = [
            c
            for c in alert_mock.await_args_list
            if len(c.args) >= 3 and c.args[2] == "classify_unknown_rate_high"
        ]
        assert len(unknown_calls) == 0

    @pytest.mark.asyncio
    async def test_classify_unknown_below_min_classified_no_alert(self) -> None:
        mp_id = uuid4()
        crawler = disc.DiscoveryOrchestrator(MagicMock(), MagicMock())
        urls = [f"https://shop.example/p/{index}" for index in range(9)]

        crawler._classify_and_resolve_url = AsyncMock(
            return_value=("unknown", "https://shop.example/p/x", False),
        )

        with patch(
            "app.modules.discovery.alerting.emit_discovery_service_alert",
            new_callable=AsyncMock,
        ) as alert_mock:
            await crawler._filter_urls_by_role(
                urls,
                requires_js=False,
                scrape_tier=1,
                marketplace_id=mp_id,
            )

        unknown_calls = [
            c
            for c in alert_mock.await_args_list
            if len(c.args) >= 3 and c.args[2] == "classify_unknown_rate_high"
        ]
        assert len(unknown_calls) == 0

    @pytest.mark.asyncio
    async def test_normal_classify_no_unknown_alert(self) -> None:
        mp_id = uuid4()
        crawler = disc.DiscoveryOrchestrator(MagicMock(), MagicMock())
        urls = [
            "https://shop.example/p/1",
            "https://shop.example/p/2",
            "https://shop.example/collections/all",
        ]

        async def classify_side_effect(url: str, **kwargs):
            if "/collections/" in url:
                return "listing", url, False
            return "product", url, False

        crawler._classify_and_resolve_url = AsyncMock(side_effect=classify_side_effect)

        with patch(
            "app.modules.discovery.alerting.emit_discovery_service_alert",
            new_callable=AsyncMock,
        ) as alert_mock:
            accepted, stats = await crawler._filter_urls_by_role(
                urls,
                requires_js=False,
                scrape_tier=1,
                marketplace_id=mp_id,
            )

        assert stats["accepted"] == 2
        unknown_calls = [
            c
            for c in alert_mock.await_args_list
            if len(c.args) >= 3 and c.args[2] == "classify_unknown_rate_high"
        ]
        assert len(unknown_calls) == 0
