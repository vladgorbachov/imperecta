"""Deep unit coverage for Celery scraper tasks (DB/pool mocked)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.modules.scraper import tasks as scraper_tasks
from app.modules.scraper.discovery import DiscoveryResult
from app.modules.scraper.scraper_pool import PoolScrapeResult


def test_discover_all_marketplaces_mocked_engine(monkeypatch):
    from datetime import datetime, timezone

    from app.modules.marketplaces.service import MarketplacePoolService

    disposed: list[bool] = []

    class Eng:
        async def dispose(self):
            disposed.append(True)

    mp = MagicMock()
    mp.id = uuid4()
    mp.is_active = True
    mp.marketplace_code = "z"

    exec_result = MagicMock()
    exec_result.scalars.return_value.all.return_value = [mp]

    db = MagicMock()
    db.execute = AsyncMock(return_value=exec_result)

    class CM:
        async def __aenter__(self):
            return db

        async def __aexit__(self, *_a):
            return False

    def factory():
        return CM()

    monkeypatch.setattr(scraper_tasks, "_make_session_factory", lambda: (Eng(), factory))
    monkeypatch.setattr(MarketplacePoolService, "recalculate_all_quotas", AsyncMock())

    async def fake_discover(self, marketplace):
        return DiscoveryResult(
            marketplace_id=marketplace.id,
            status="completed",
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            persisted_listings=0,
        )

    monkeypatch.setattr(
        "app.modules.scraper.discovery.DiscoveryCrawler.discover",
        fake_discover,
    )

    out = scraper_tasks.discover_all_marketplaces.run()
    assert out["marketplaces_seen"] == 1
    assert out["dispatched"] == 1
    assert disposed


def test_discover_all_marketplace_loop_exception(monkeypatch):
    from datetime import datetime, timezone

    from app.modules.marketplaces.service import MarketplacePoolService

    class Eng:
        async def dispose(self):
            pass

    mp = MagicMock()
    mp.id = uuid4()
    exec_result = MagicMock()
    exec_result.scalars.return_value.all.return_value = [mp]

    db = MagicMock()
    db.execute = AsyncMock(return_value=exec_result)

    class CM:
        async def __aenter__(self):
            return db

        async def __aexit__(self, *_a):
            return False

    monkeypatch.setattr(scraper_tasks, "_make_session_factory", lambda: (Eng(), lambda: CM()))
    monkeypatch.setattr(MarketplacePoolService, "recalculate_all_quotas", AsyncMock())

    async def boom(self, _m):
        raise RuntimeError("discover boom")

    monkeypatch.setattr(
        "app.modules.scraper.discovery.DiscoveryCrawler.discover",
        boom,
    )

    out = scraper_tasks.discover_all_marketplaces.run()
    assert out["errors"]


def test_discover_single_not_found_mocked(monkeypatch):
    class Eng:
        async def dispose(self):
            pass

    db = MagicMock()
    db.get = AsyncMock(return_value=None)

    class CM:
        async def __aenter__(self):
            return db

        async def __aexit__(self, *_a):
            return False

    monkeypatch.setattr(scraper_tasks, "_make_session_factory", lambda: (Eng(), lambda: CM()))

    out = scraper_tasks.discover_single_marketplace.run("00000000-0000-0000-0000-000000000001")
    assert out["status"] == "not_found"


def test_discover_single_success_mocked(monkeypatch):
    from datetime import datetime, timezone

    mp = MagicMock()
    mp.id = uuid4()

    class Eng:
        async def dispose(self):
            pass

    db = MagicMock()
    db.get = AsyncMock(return_value=mp)

    class CM:
        async def __aenter__(self):
            return db

        async def __aexit__(self, *_a):
            return False

    monkeypatch.setattr(scraper_tasks, "_make_session_factory", lambda: (Eng(), lambda: CM()))

    async def ok_discover(self, marketplace):
        return DiscoveryResult(
            marketplace_id=marketplace.id,
            status="completed",
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            persisted_listings=2,
        )

    monkeypatch.setattr(
        "app.modules.scraper.discovery.DiscoveryCrawler.discover",
        ok_discover,
    )

    out = scraper_tasks.discover_single_marketplace.run(str(mp.id))
    assert out["status"] == "completed"
    assert out["products_new"] == 2


def test_run_scrape_all_pool_impl_counts_failed_without_exception(monkeypatch):
    lid = uuid4()
    listing = MagicMock()
    listing.external_url = "https://example.com/p"

    db = MagicMock()
    row_result = MagicMock()
    row_result.all.return_value = [(lid,)]
    db.execute.return_value = row_result
    db.get.return_value = listing

    monkeypatch.setattr(scraper_tasks, "sync_session_factory", lambda: db)
    monkeypatch.setattr(
        "app.modules.scraper.service.GlobalScrapeService.scrape_product",
        lambda self, x: PoolScrapeResult(success=False, url="https://example.com/p", error="fetch_failed"),
    )

    out = scraper_tasks._run_scrape_all_pool_impl()
    assert out["scraped_failed"] == 1


def test_run_scrape_all_pool_impl_happy_path(monkeypatch):
    lid = uuid4()
    listing = MagicMock()
    listing.external_url = "https://example.com/p"

    db = MagicMock()
    row_result = MagicMock()
    row_result.all.return_value = [(lid,)]
    db.execute.return_value = row_result
    db.get.return_value = listing

    monkeypatch.setattr(scraper_tasks, "sync_session_factory", lambda: db)
    monkeypatch.setattr(
        "app.modules.scraper.service.GlobalScrapeService.scrape_product",
        lambda self, x: PoolScrapeResult(success=True, url="https://example.com/p"),
    )

    out = scraper_tasks._run_scrape_all_pool_impl()
    assert out["queued"] == 1
    assert out["scraped_ok"] == 1
    assert out["scraped_failed"] == 0


def test_run_scrape_all_pool_impl_listing_failure_persists(monkeypatch):
    lid = uuid4()
    listing = MagicMock()
    listing.external_url = "https://example.com/p"

    db = MagicMock()
    row_result = MagicMock()
    row_result.all.return_value = [(lid,)]
    db.execute.return_value = row_result
    db.get.return_value = listing

    monkeypatch.setattr(scraper_tasks, "sync_session_factory", lambda: db)

    def boom(self, x):
        raise ValueError("scrape failed")

    monkeypatch.setattr(
        "app.modules.scraper.service.GlobalScrapeService.scrape_product",
        boom,
    )
    persisted: list[tuple] = []

    def capture_persist(uid, tb):
        persisted.append((uid, tb))

    monkeypatch.setattr(scraper_tasks, "_persist_technical_error_log", capture_persist)

    out = scraper_tasks._run_scrape_all_pool_impl()
    assert out["scraped_failed"] == 1
    assert persisted and persisted[0][0] == lid


def test_scrape_all_pool_products_task_runs(monkeypatch):
    monkeypatch.setattr(
        scraper_tasks,
        "_run_scrape_all_pool",
        lambda: {"queued": 0, "scraped_ok": 0, "scraped_failed": 0},
    )
    out = scraper_tasks.scrape_all_pool_products.run()
    assert out["queued"] == 0


def test_scrape_all_alias(monkeypatch):
    monkeypatch.setattr(
        scraper_tasks,
        "_run_scrape_all_pool",
        lambda: {"queued": 1},
    )
    assert scraper_tasks.scrape_all()["queued"] == 1


def test_check_pool_completeness_mocked(monkeypatch):
    db = MagicMock()
    db.close = MagicMock()
    monkeypatch.setattr(scraper_tasks, "sync_session_factory", lambda: db)
    monkeypatch.setattr(
        "app.modules.scraper.service.GlobalScrapeService.find_incomplete_products",
        lambda self, limit: [uuid4(), uuid4()],
    )
    out = scraper_tasks.check_pool_completeness.run()
    assert out["checked"] == 2
    db.close.assert_called()
