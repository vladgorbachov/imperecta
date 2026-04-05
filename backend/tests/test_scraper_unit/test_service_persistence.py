"""Unit tests for GlobalScrapeService persistence rules (sync session mocked where needed)."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest

from app.models.dimensions import DimMarketplace, DimProduct
from app.models.facts import FactListing
from app.modules.scraper.extractors import ExtractedProduct
from app.modules.scraper.scraper_pool import PoolScrapeResult, ScraperPool
from app.modules.scraper.service import GlobalScrapeService


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
    listing.last_error = "old"
    listing.consecutive_errors = 5
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


def test_scrape_resets_errors_before_worker(monkeypatch):
    """Stale last_error / consecutive_errors cleared before pool I/O."""
    listing_id = uuid.uuid4()
    product_id = uuid.uuid4()
    marketplace_id = uuid.uuid4()
    session, listing = _session_with_listing(
        listing_id=listing_id,
        product_id=product_id,
        marketplace_id=marketplace_id,
    )
    seen: dict[str, int] = {}

    def capture_worker(coro):
        seen["ce"] = listing.consecutive_errors
        seen["le"] = 0 if listing.last_error is None else 1
        import inspect

        if inspect.iscoroutine(coro):
            coro.close()
        return PoolScrapeResult(
            success=False,
            url=listing.external_url,
            error="fetch_failed:httpx",
        )

    monkeypatch.setattr("app.modules.scraper.service._run_coro_in_worker", capture_worker)
    svc = GlobalScrapeService(session, MagicMock(spec=ScraperPool))
    svc.scrape_product(listing_id)
    assert seen.get("ce") == 0
    assert seen.get("le") == 0


def test_log_status_set_on_result(monkeypatch):
    """PoolScrapeResult.log_status reflects _determine_log_status after persist."""
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
            data=ExtractedProduct(title="T", price=10.0, currency="USD"),
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


def test_fact_price_skipped_without_currency(monkeypatch):
    """Quality gate: no FactPrice row without currency even if price present."""
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
