"""Edge paths in GlobalScrapeService (mock session where needed)."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest

from app.models.dimensions import DimMarketplace, DimProduct
from app.models.facts import FactListing
from app.modules.scraper.extractors import ExtractedProduct
from app.modules.scraper.scraper_pool import PoolScrapeResult, ScraperPool
from app.modules.scraper.service import GlobalScrapeService, _run_coro_in_worker
from fixtures.scraper_fixtures import _fake_run_coro


def test_listing_not_found_returns_early():
    session = MagicMock()
    session.get.return_value = None
    svc = GlobalScrapeService(session, MagicMock(spec=ScraperPool))
    out = svc.scrape_product(uuid.uuid4())
    assert out.success is False and out.error == "listing_not_found"


def test_run_coro_in_worker_runs():
    async def coro():
        return 99

    assert _run_coro_in_worker(coro()) == 99


def test_run_coro_in_worker_ignores_shutdown_asyncgen_error(monkeypatch):
    import asyncio

    from app.modules.scraper.service import _run_coro_in_worker

    loop = asyncio.new_event_loop()

    async def boom():
        raise RuntimeError("asyncgen shutdown")

    loop.shutdown_asyncgens = boom  # type: ignore[method-assign]
    monkeypatch.setattr(asyncio, "new_event_loop", lambda: loop)
    monkeypatch.setattr(asyncio, "set_event_loop", lambda _x: None)

    async def coro():
        return 42

    assert _run_coro_in_worker(coro()) == 42


def test_persist_commit_failure(monkeypatch):
    listing_id = uuid.uuid4()
    product_id = uuid.uuid4()
    marketplace_id = uuid.uuid4()
    listing = FactListing(
        id=listing_id,
        product_id=product_id,
        marketplace_id=marketplace_id,
        external_url="https://example.com/i",
        url_hash=FactListing.compute_url_hash("https://example.com/i"),
    )
    product = DimProduct(id=product_id, name="p", name_normalized="p")
    mp = DimMarketplace(
        id=marketplace_id,
        marketplace_code="m1",
        name="M",
        source_type="direct_retail",
        country_code="US",
        operates_in=["US"],
        domain="example.com",
        base_url="https://example.com",
        currency_code="USD",
        scraper_type="httpx",
    )
    session = MagicMock()

    def get_side(model, pk):
        if model is FactListing and pk == listing_id:
            return listing
        if model is DimProduct and pk == product_id:
            return product
        if model is DimMarketplace and pk == marketplace_id:
            return mp
        return None

    session.get.side_effect = get_side
    session.add = MagicMock()
    session.execute = MagicMock()
    session.flush = MagicMock()
    session.commit = MagicMock(side_effect=RuntimeError("commit failed"))
    session.rollback = MagicMock()

    monkeypatch.setattr(
        "app.modules.scraper.service._run_coro_in_worker",
        _fake_run_coro(
            PoolScrapeResult(
                success=True,
                url="https://example.com/i",
                data=ExtractedProduct(title="T", price=5.0, currency="USD"),
                scraper_layer="httpx",
            ),
        ),
    )
    monkeypatch.setattr("app.modules.scraper.service._today_date_id", lambda _db: 20260401)

    svc = GlobalScrapeService(session, MagicMock(spec=ScraperPool))
    out = svc.scrape_product(listing_id)
    assert out.success is False and out.error == "persist_failed"
    session.rollback.assert_called()


@pytest.mark.integration
def test_get_stale_and_incomplete_from_db():
    from app.database import sync_session_factory
    from fixtures.scraper_fixtures import _pg_available

    if not _pg_available():
        pytest.skip("PostgreSQL required")
    db = sync_session_factory()
    try:
        pool = ScraperPool()
        svc = GlobalScrapeService(db, pool)
        assert isinstance(svc.get_stale_products(3), list)
        assert isinstance(svc.find_incomplete_products(3), list)
    finally:
        db.close()
