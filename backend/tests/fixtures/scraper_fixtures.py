"""Shared fixtures for scraper unit/integration tests."""

from __future__ import annotations

import inspect
import uuid

import pytest
from sqlalchemy import text

from app.models.dimensions import DimCountry, DimCurrency, DimMarketplace, DimProduct
from app.models.facts import FactListing
from app.modules.scraper.scraper_pool import PoolScrapeResult


def _fake_run_coro(result: PoolScrapeResult):
    """Return fixed scrape result; close pool coroutine to avoid RuntimeWarning."""

    def _inner(coro):
        if inspect.iscoroutine(coro):
            coro.close()
        return result

    return _inner


def _pg_available() -> bool:
    try:
        from app.database import sync_engine

        with sync_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


@pytest.fixture
def pg_session():
    if not _pg_available():
        pytest.skip("PostgreSQL unavailable (set DATABASE_URL for integration tests)")
    from sqlalchemy.orm import Session

    from app.database import sync_engine

    conn = sync_engine.connect()
    trans = conn.begin()
    session = Session(bind=conn)
    try:
        yield session
    finally:
        trans.rollback()
        session.close()
        conn.close()


def _ensure_currency(session, code: str = "USD") -> None:
    from app.models.dimensions import DimCurrency

    if session.get(DimCurrency, code):
        return
    session.add(
        DimCurrency(
            currency_code=code,
            name="US Dollar",
            symbol="$",
        ),
    )
    session.flush()


def _ensure_country(session, code: str = "US") -> None:
    if session.get(DimCountry, code):
        return
    session.add(
        DimCountry(
            country_code=code,
            name="United States",
            region="Other",
            currency_code="USD",
        ),
    )
    session.flush()


def _seed_listing(session) -> uuid.UUID:
    _ensure_currency(session)
    _ensure_country(session)
    suffix = uuid.uuid4().hex[:12]
    mp_code = f"mp_persist_{suffix}"
    mp = DimMarketplace(
        marketplace_code=mp_code,
        name="Test MP",
        source_type="direct_retail",
        country_code="US",
        operates_in=["US"],
        domain="example.com",
        base_url="https://example.com",
        currency_code="USD",
        scraper_type="httpx",
    )
    session.add(mp)
    session.flush()

    product_id = uuid.uuid4()
    product = DimProduct(
        id=product_id,
        name="product",
        name_normalized="product",
    )
    session.add(product)
    session.flush()

    listing_id = uuid.uuid4()
    url = f"https://example.com/p/{suffix}"
    listing = FactListing(
        id=listing_id,
        product_id=product_id,
        marketplace_id=mp.id,
        external_url=url,
        url_hash=FactListing.compute_url_hash(url),
    )
    session.add(listing)
    session.flush()
    return listing_id
