"""D4 READONLY-CRASH: pulse swallow + read-only-aware scrape persistence."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import OperationalError

from app.modules.scraper import service as scraper_service
from app.modules.scraper.extractors import ExtractedProduct
from app.modules.scraper.pipeline import activity_pulse
from app.modules.scraper.scraper_pool import PoolScrapeResult, ScraperPool
from app.modules.scraper.service import GlobalScrapeService, _is_read_only_error


class _ReadOnlySqlTransaction(Exception):
    pgcode = "25006"


def _session_with_listing(
    *,
    listing_id: uuid.UUID,
    product_id: uuid.UUID,
    marketplace_id: uuid.UUID,
) -> tuple[MagicMock, object]:
    from app.models.dimensions import DimMarketplace, DimProduct
    from app.models.facts import FactListing

    listing = FactListing(
        id=listing_id,
        product_id=product_id,
        marketplace_id=marketplace_id,
        external_url="https://example.com/item",
        url_hash=FactListing.compute_url_hash("https://example.com/item"),
    )
    listing.last_checked_at = None
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
    session.connection = MagicMock()
    return session, listing


def test_child_pulse_swallows_readonly(monkeypatch):
    job_id = uuid.uuid4()
    job = MagicMock()
    job.config = {"metadata": {}}

    db = MagicMock()
    db.get.return_value = job
    db.commit.side_effect = OperationalError(
        "stmt",
        {},
        _ReadOnlySqlTransaction("cannot execute UPDATE in a read-only transaction"),
    )
    db.close = MagicMock()

    monkeypatch.setattr(activity_pulse, "sync_session_factory", lambda: db)
    monkeypatch.setattr(activity_pulse, "should_pulse_db", lambda *_a, **_k: True)
    monkeypatch.setattr(activity_pulse, "push_relay_line", lambda *_a, **_k: None)

    activity_pulse.pulse_job_activity_sync(job_id, "line", force_db=True)

    db.close.assert_called_once()


def test_is_read_only_error():
    ro = OperationalError(
        "stmt",
        {},
        _ReadOnlySqlTransaction("read-only transaction"),
    )
    assert _is_read_only_error(ro) is True
    assert _is_read_only_error(ValueError("nope")) is False
    assert _is_read_only_error(OperationalError("x", {}, Exception("other"))) is False


def test_scrape_listing_readonly_does_not_advance_last_checked(monkeypatch):
    listing_id = uuid.uuid4()
    product_id = uuid.uuid4()
    marketplace_id = uuid.uuid4()
    session, listing = _session_with_listing(
        listing_id=listing_id,
        product_id=product_id,
        marketplace_id=marketplace_id,
    )
    session.commit.side_effect = OperationalError(
        "stmt",
        {},
        _ReadOnlySqlTransaction("read-only"),
    )
    invalidate = MagicMock()
    monkeypatch.setattr(scraper_service, "invalidate_sync_session", invalidate)

    def fail_worker(coro):
        import inspect

        if inspect.iscoroutine(coro):
            coro.close()
        return PoolScrapeResult(
            success=False,
            url="https://example.com/item",
            error="fetch_failed:httpx",
            data=None,
        )

    monkeypatch.setattr("app.modules.scraper.service._run_coro_in_worker", fail_worker)

    svc = GlobalScrapeService(session, MagicMock(spec=ScraperPool))
    out = svc.scrape_product(listing_id)

    assert out.success is False
    assert out.error == "read_only_retriable"
    assert listing.last_checked_at is None
    invalidate.assert_called_once()


def test_scrape_listing_success_advances_last_checked(monkeypatch):
    listing_id = uuid.uuid4()
    product_id = uuid.uuid4()
    marketplace_id = uuid.uuid4()
    session, listing = _session_with_listing(
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
    assert listing.last_checked_at is not None


def test_scrape_listing_honest_absent_advances_last_checked(monkeypatch):
    listing_id = uuid.uuid4()
    product_id = uuid.uuid4()
    marketplace_id = uuid.uuid4()
    session, listing = _session_with_listing(
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
    assert listing.last_checked_at is not None


def test_scrape_listing_technical_persist_failure_does_not_advance(monkeypatch):
    listing_id = uuid.uuid4()
    product_id = uuid.uuid4()
    marketplace_id = uuid.uuid4()
    session, listing = _session_with_listing(
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
            error="fetch_failed:httpx",
            data=None,
        )

    monkeypatch.setattr("app.modules.scraper.service._run_coro_in_worker", fail_worker)
    session.commit.side_effect = RuntimeError("disk full")

    svc = GlobalScrapeService(session, MagicMock(spec=ScraperPool))
    out = svc.scrape_product(listing_id)

    assert out.error == "persist_failed"
    assert listing.last_checked_at is None
