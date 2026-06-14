"""Exercise Celery task entrypoints (sync .run) and task helpers."""

from __future__ import annotations

from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

import pytest

from app.modules.scraper import tasks as scraper_tasks


def test_run_async_executes_coro():
    async def add_one():
        return 41

    assert scraper_tasks._run_async(add_one()) == 41


def test_legacy_tasks_removed():
    assert not hasattr(scraper_tasks, "scrape_single")
    assert not hasattr(scraper_tasks, "scrape_user_products")
    assert not hasattr(scraper_tasks, "scrape_all")


@pytest.mark.integration
def test_discover_single_marketplace_unknown_id():
    from fixtures.scraper_fixtures import _pg_available

    if not _pg_available():
        pytest.skip("PostgreSQL required")
    out = scraper_tasks.discover_single_marketplace.run("00000000-0000-0000-0000-000000000099")
    assert out.get("status") == "not_found"


def test_run_scrape_all_pool_outer_technical_error(monkeypatch):
    # Mock signature mirrors production exactly:
    #   _run_scrape_all_pool_impl(scrape_job_id=None, *, marketplace_codes=None)
    # so that the production call site (which passes scrape_job_id and
    # marketplace_codes by keyword) reaches the lambda body and raises
    # RuntimeError("boom"); the outer-except path then surfaces
    # error="technical_error" with "boom" in the traceback.
    monkeypatch.setattr(
        scraper_tasks,
        "_run_scrape_all_pool_impl",
        lambda scrape_job_id=None, *, marketplace_codes=None: (
            _ for _ in ()
        ).throw(RuntimeError("boom")),
    )
    out = scraper_tasks._run_scrape_all_pool()
    assert out.get("error") == "technical_error" and "boom" in (out.get("traceback") or "")


@pytest.mark.integration
def test_fast_scrape_all_pool_one_listing(monkeypatch):
    from app.database import sync_session_factory
    from app.modules.scraper.scraper_pool import ScraperPool
    from app.modules.scraper.service import GlobalScrapeService

    from fixtures.scraper_fixtures import _pg_available, load_active_listings_from_db

    if not _pg_available():
        pytest.skip("PostgreSQL required")
    rows = load_active_listings_from_db(1)
    if not rows:
        pytest.skip("No listings in database for fast scrape test")

    lid = rows[0].id

    def _one_only():
        db = sync_session_factory()
        scraper_pool = ScraperPool()
        try:
            svc = GlobalScrapeService(db, scraper_pool)
            r = svc.scrape_product(lid)
            ok = 1 if r.success else 0
            fail = 0 if r.success else 1
            return {"queued": 1, "scraped_ok": ok, "scraped_failed": fail}
        finally:
            db.close()

    monkeypatch.setattr(scraper_tasks, "_run_scrape_all_pool_impl", _one_only)
    out = scraper_tasks._run_scrape_all_pool()
    assert out["queued"] == 1
    assert out["scraped_ok"] + out["scraped_failed"] == 1


@pytest.mark.integration
def test_scrape_pool_product_impl_runs(monkeypatch):
    from fixtures.scraper_fixtures import _pg_available, load_active_listings_from_db

    if not _pg_available():
        pytest.skip("PostgreSQL required")
    rows = load_active_listings_from_db(1)
    if not rows:
        pytest.skip("No listings in database")
    out = scraper_tasks._scrape_pool_product_impl(str(rows[0].id))
    assert "success" in out and "listing_id" in out


def test_scrape_pool_product_outer_technical(monkeypatch):
    monkeypatch.setattr(
        scraper_tasks,
        "_scrape_pool_product_impl",
        lambda _lid: (_ for _ in ()).throw(ValueError("inner")),
    )
    monkeypatch.setattr(scraper_tasks, "_persist_technical_error_log", lambda *a, **k: None)
    out = scraper_tasks.scrape_pool_product.run(str(uuid4()))
    assert out.get("error") == "technical_error"


@pytest.mark.integration
def test_check_pool_completeness_run():
    from fixtures.scraper_fixtures import _pg_available

    if not _pg_available():
        pytest.skip("PostgreSQL required")
    out = scraper_tasks.check_pool_completeness.run()
    assert "checked" in out and "listing_ids" in out


@pytest.mark.integration
def test_discover_all_marketplaces_smoke(monkeypatch):
    """Runs discover loop; crawler.discover may be no-op fast when marketplace list empty."""
    from fixtures.scraper_fixtures import _pg_available

    if not _pg_available():
        pytest.skip("PostgreSQL required")

    async def fake_discover(self, marketplace):
        from datetime import datetime, timezone

        from app.modules.scraper.discovery import DiscoveryResult

        return DiscoveryResult(
            marketplace_id=marketplace.id,
            status="completed",
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            persisted_listings=0,
        )

    monkeypatch.setattr("app.modules.scraper.discovery.DiscoveryCrawler.discover", fake_discover)
    out = scraper_tasks.discover_all_marketplaces.run()
    assert "marketplaces_seen" in out and "errors" in out
