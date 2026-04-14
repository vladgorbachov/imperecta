"""Unit tests: scrape_product gates, title-only success, price_not_found, dim_date idempotency."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest

from app.models.dimensions import DimMarketplace, DimProduct
from app.models.facts import FactListing
from app.modules.scraper.extractors import ExtractedProduct
from app.modules.scraper.scraper_pool import PoolScrapeResult, ScraperPool
from app.modules.scraper.service import GlobalScrapeService, _today_date_id
from fixtures.scraper_fixtures import _pg_available, pg_session


def _session_with_listing(
    *,
    listing_id: uuid.UUID,
    product_id: uuid.UUID,
    marketplace_id: uuid.UUID,
) -> tuple[MagicMock, FactListing]:
    listing = FactListing(
        id=listing_id,
        product_id=product_id,
        marketplace_id=marketplace_id,
        external_url="https://example.com/item",
        url_hash=FactListing.compute_url_hash("https://example.com/item"),
    )
    product = DimProduct(
        id=product_id,
        name="product",
        name_normalized="product",
    )
    mp = DimMarketplace(
        id=marketplace_id,
        marketplace_code=f"mp_{uuid.uuid4().hex[:8]}",
        name="MP",
        source_type="direct_retail",
        country_code="US",
        operates_in=["US"],
        domain="example.com",
        base_url="https://example.com",
        currency_code="USD",
        scraper_type="httpx",
    )
    session = MagicMock()

    def get_side_effect(model, pk):
        if model is FactListing and pk == listing_id:
            return listing
        if model is DimProduct and pk == product_id:
            return product
        if model is DimMarketplace and pk == marketplace_id:
            return mp
        return None

    session.get.side_effect = get_side_effect
    session.add = MagicMock()
    session.execute = MagicMock()
    session.flush = MagicMock()
    session.commit = MagicMock()
    session.rollback = MagicMock()
    return session, listing


def test_scrape_product_success_with_title_only(monkeypatch):
    """Title (no product_name field) + price + currency yields success log status."""
    listing_id = uuid.uuid4()
    product_id = uuid.uuid4()
    marketplace_id = uuid.uuid4()
    session, _listing = _session_with_listing(
        listing_id=listing_id,
        product_id=product_id,
        marketplace_id=marketplace_id,
    )

    def ok_worker(coro):
        import inspect

        if inspect.iscoroutine(coro):
            coro.close()
        return PoolScrapeResult(
            success=True,
            url="https://example.com/item",
            data=ExtractedProduct(title="Title Only Name", price=9.99, currency="USD"),
            scraper_layer="httpx",
        )

    monkeypatch.setattr("app.modules.scraper.service._run_coro_in_worker", ok_worker)
    monkeypatch.setattr("app.modules.scraper.service._today_date_id", lambda _db: 20990101)
    monkeypatch.setattr(
        "app.modules.scraper.service._previous_price_snapshot",
        lambda *_a, **_k: None,
    )
    svc = GlobalScrapeService(session, MagicMock(spec=ScraperPool))
    out = svc.scrape_product(listing_id)
    assert out.log_status == "success"


def test_scrape_product_price_not_found(monkeypatch):
    """Pool failure price_not_found maps to scrape_logs status."""
    listing_id = uuid.uuid4()
    product_id = uuid.uuid4()
    marketplace_id = uuid.uuid4()
    session, _listing = _session_with_listing(
        listing_id=listing_id,
        product_id=product_id,
        marketplace_id=marketplace_id,
    )

    def fail_worker(coro):
        import inspect

        if inspect.iscoroutine(coro):
            coro.close()
        return PoolScrapeResult(
            success=False,
            url="https://example.com/item",
            error="price_not_found",
            data=None,
        )

    monkeypatch.setattr("app.modules.scraper.service._run_coro_in_worker", fail_worker)
    svc = GlobalScrapeService(session, MagicMock(spec=ScraperPool))
    out = svc.scrape_product(listing_id)
    assert out.log_status == "price_not_found"


def test_persistence_gates(monkeypatch):
    """PERSISTENCE GATE: missing currency blocks FactPrice snapshot."""
    listing_id = uuid.uuid4()
    product_id = uuid.uuid4()
    marketplace_id = uuid.uuid4()
    session, _listing = _session_with_listing(
        listing_id=listing_id,
        product_id=product_id,
        marketplace_id=marketplace_id,
    )

    def ok_worker(coro):
        import inspect

        if inspect.iscoroutine(coro):
            coro.close()
        return PoolScrapeResult(
            success=True,
            url="https://example.com/item",
            data=ExtractedProduct(title="T", price=10.0, currency=None),
            scraper_layer="httpx",
            missing_fields=["currency"],
        )

    monkeypatch.setattr("app.modules.scraper.service._run_coro_in_worker", ok_worker)
    monkeypatch.setattr("app.modules.scraper.service._today_date_id", lambda _db: 20990101)
    svc = GlobalScrapeService(session, MagicMock(spec=ScraperPool))
    out = svc.scrape_product(listing_id)
    assert out.log_status == "missing_critical_data"
    from app.models.facts import FactPrice

    added = [c.args[0] for c in session.add.call_args_list if c.args]
    assert not any(isinstance(x, FactPrice) for x in added)


@pytest.mark.integration
def test_today_date_id_idempotency(pg_session):
    """Two calls on the same session return the same date_id (dim_date row stable)."""
    if not _pg_available():
        pytest.skip("PostgreSQL unavailable")

    first = _today_date_id(pg_session)
    second = _today_date_id(pg_session)
    assert first == second
