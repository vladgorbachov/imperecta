"""Integration: seeded listing + mocked pool → fact_price and scrape_logs rows."""

from __future__ import annotations

import inspect

import pytest
from sqlalchemy import func, select

from app.models.app_tables import ScrapeLog
from app.models.facts import FactPrice
from app.modules.scraper.extractors import ExtractedProduct
from app.modules.scraper.scraper_pool import PoolScrapeResult, ScraperPool
from app.modules.scraper.service import GlobalScrapeService

from fixtures.scraper_fixtures import _pg_available, _seed_listing


def _make_ok_worker(
    title: str = "Pipeline Product",
    price: float = 42.0,
    currency: str = "USD",
    currency_raw: str | None = "USD",
    price_raw_text: str | None = "42.00",
):
    def ok_worker(coro):
        if inspect.iscoroutine(coro):
            coro.close()
        return PoolScrapeResult(
            success=True,
            url="https://example.com/p/item",
            data=ExtractedProduct(
                title=title,
                price=price,
                currency=currency,
                currency_raw=currency_raw,
                price_raw_text=price_raw_text,
            ),
            scraper_layer="httpx",
            duration_ms=12,
        )

    return ok_worker


@pytest.mark.integration
def test_full_scrape_pipeline(monkeypatch):
    """GlobalScrapeService with deterministic pool output persists price + log rows."""
    if not _pg_available():
        pytest.skip("PostgreSQL required")

    from app.database import sync_session_factory

    db = sync_session_factory()
    listing_id = None
    try:
        listing_id = _seed_listing(db)
        db.commit()

        monkeypatch.setattr(
            "app.modules.scraper.service._run_coro_in_worker",
            _make_ok_worker(),
        )
        pool = ScraperPool()
        svc = GlobalScrapeService(db, pool)
        out = svc.scrape_product(listing_id)
        assert out.success is True

        n_price = db.execute(
            select(func.count()).select_from(FactPrice).where(FactPrice.listing_id == listing_id),
        ).scalar_one()
        n_log = db.execute(
            select(func.count()).select_from(ScrapeLog).where(ScrapeLog.listing_id == listing_id),
        ).scalar_one()
        assert int(n_price) >= 1
        assert int(n_log) >= 1

        last_log = db.execute(
            select(ScrapeLog)
            .where(ScrapeLog.listing_id == listing_id)
            .order_by(ScrapeLog.created_at.desc())
            .limit(1),
        ).scalar_one_or_none()
        assert last_log is not None
        assert last_log.status == "success"
    finally:
        db.close()


@pytest.mark.integration
def test_full_scrape_pipeline_eu_price(monkeypatch):
    """EU-formatted price (comma decimal, EUR) persists correctly."""
    if not _pg_available():
        pytest.skip("PostgreSQL required")

    from app.database import sync_session_factory

    db = sync_session_factory()
    try:
        listing_id = _seed_listing(db)
        db.commit()

        monkeypatch.setattr(
            "app.modules.scraper.service._run_coro_in_worker",
            _make_ok_worker(
                title="Kühlschrank Bosch",
                price=599.99,
                currency="EUR",
                currency_raw="EUR",
                price_raw_text="599,99 €",
            ),
        )
        svc = GlobalScrapeService(db, ScraperPool())
        out = svc.scrape_product(listing_id)
        assert out.success is True

        fp = db.execute(
            select(FactPrice).where(FactPrice.listing_id == listing_id).limit(1),
        ).scalar_one_or_none()
        assert fp is not None
        assert fp.currency_code == "EUR"
        assert float(fp.price) == pytest.approx(599.99, abs=0.01)
    finally:
        db.close()
