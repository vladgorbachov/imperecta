"""Integration: discovery DB URLs → scrape → scrape_logs (+ fact_price when quality gate passes)."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

import pytest
from sqlalchemy import func, select

from app.models.app_tables import ScrapeLog
from app.models.facts import FactListing, FactPrice
from app.modules.scraper.scraper_pool import ScraperPool
from app.modules.scraper.service import GlobalScrapeService
from fixtures.scraper_fixtures import _pg_available, load_active_listings_from_db


@pytest.fixture(scope="module")
def sample_listing_row():
    if not _pg_available():
        pytest.skip("PostgreSQL required")
    rows = load_active_listings_from_db(3)
    if not rows:
        pytest.skip("No active listings in fact_listing (run discovery first)")
    return rows[0]


@pytest.mark.integration
def test_live_scrape_creates_scrape_log(sample_listing_row: object):
    """Full service path writes at least one ScrapeLog for the listing."""
    from app.database import sync_session_factory

    listing_id: UUID = sample_listing_row.id
    db = sync_session_factory()
    try:
        before = db.execute(
            select(func.count()).select_from(ScrapeLog).where(ScrapeLog.listing_id == listing_id),
        ).scalar_one()
        pool = ScraperPool()
        svc = GlobalScrapeService(db, pool)
        out = svc.scrape_product(listing_id)
        assert hasattr(out, "success")
        after = db.execute(
            select(func.count()).select_from(ScrapeLog).where(ScrapeLog.listing_id == listing_id),
        ).scalar_one()
        assert int(after) >= int(before) + 1
        last = db.execute(
            select(ScrapeLog)
            .where(ScrapeLog.listing_id == listing_id)
            .order_by(ScrapeLog.created_at.desc())
            .limit(1),
        ).scalar_one_or_none()
        assert last is not None
        assert last.status in (
            "success",
            "error",
            "timeout",
            "blocked",
            "captcha",
            "not_found",
            "price_not_found",
            "parse_error",
            "missing_critical_data",
            "technical_error",
        )
    finally:
        db.close()


@pytest.mark.integration
def test_idempotent_second_scrape_second_log(sample_listing_row: object):
    """Two scrapes of the same listing append two ScrapeLog rows (no silent skip)."""
    from app.database import sync_session_factory

    listing_id: UUID = sample_listing_row.id
    db = sync_session_factory()
    try:
        pool = ScraperPool()
        svc = GlobalScrapeService(db, pool)
        c1 = db.execute(
            select(func.count()).select_from(ScrapeLog).where(ScrapeLog.listing_id == listing_id),
        ).scalar_one()
        svc.scrape_product(listing_id)
        c2 = db.execute(
            select(func.count()).select_from(ScrapeLog).where(ScrapeLog.listing_id == listing_id),
        ).scalar_one()
        svc.scrape_product(listing_id)
        c3 = db.execute(
            select(func.count()).select_from(ScrapeLog).where(ScrapeLog.listing_id == listing_id),
        ).scalar_one()
        assert int(c2) >= int(c1) + 1
        assert int(c3) >= int(c2) + 1
    finally:
        db.close()


@pytest.mark.integration
def test_fact_price_written_when_success_with_price_currency(sample_listing_row: object):
    """When scrape succeeds with title, price, currency, a FactPrice row may exist for today."""
    from app.database import sync_session_factory

    from app.models.dimensions import DimDate

    listing_id: UUID = sample_listing_row.id
    db = sync_session_factory()
    try:
        pool = ScraperPool()
        svc = GlobalScrapeService(db, pool)
        out = svc.scrape_product(listing_id)
        if not out.success or not out.data:
            pytest.skip("Live scrape did not succeed; cannot assert fact_price")
        d = out.data
        if not (d.title and d.price and d.price > 0 and d.currency):
            pytest.skip("Listing page did not yield full quality-gate fields")
        today = datetime.now(timezone.utc).date()
        date_id = int(today.strftime("%Y%m%d"))
        row = db.execute(select(DimDate.date_id).where(DimDate.date_id == date_id)).scalar_one_or_none()
        if row is None:
            pytest.skip("dim_date missing for today")
        fp = db.execute(
            select(func.count())
            .select_from(FactPrice)
            .where(FactPrice.listing_id == listing_id, FactPrice.date_id == date_id),
        ).scalar_one()
        assert int(fp) >= 1
    finally:
        db.close()
