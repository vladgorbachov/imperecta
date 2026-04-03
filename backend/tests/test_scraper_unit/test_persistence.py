"""Persistence tests for GlobalScrapeService (unit mocks; PostgreSQL optional)."""

from __future__ import annotations

import uuid
from datetime import timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from sqlalchemy import select, text

from app.models.app_tables import ScrapeLog
from app.models.dimensions import DimMarketplace, DimProduct
from app.models.facts import FactListing, FactPrice
from app.modules.scraper.extractors import ExtractedProduct
from app.modules.scraper.scraper_pool import PoolScrapeResult, ScraperPool
from app.modules.scraper.service import GlobalScrapeService, _today_date_id
from fixtures.scraper_fixtures import _fake_run_coro, _seed_listing, pg_session


def _patch_commit_flush(session) -> None:
    def _commit_flush() -> None:
        session.flush()

    session.commit = _commit_flush  # type: ignore[method-assign]


def _build_mock_scrape_session(
    listing_id: uuid.UUID,
    product_id: uuid.UUID,
    marketplace_id: uuid.UUID,
    *,
    last_error: str | None = "legacy_fetch_failed",
    consecutive_errors: int = 7,
) -> tuple[MagicMock, DimProduct, FactListing]:
    listing = FactListing(
        id=listing_id,
        product_id=product_id,
        marketplace_id=marketplace_id,
        external_url="https://example.com/item",
        url_hash=FactListing.compute_url_hash("https://example.com/item"),
    )
    listing.last_error = last_error
    listing.consecutive_errors = consecutive_errors
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
    session.commit = MagicMock()
    session.rollback = MagicMock()
    return session, product, listing


def test_scrape_product_full_success(monkeypatch):
    """Successful scrape: clears legacy errors, writes FactPrice, updates product name."""
    listing_id = uuid.uuid4()
    product_id = uuid.uuid4()
    marketplace_id = uuid.uuid4()
    session, product, listing = _build_mock_scrape_session(
        listing_id,
        product_id,
        marketplace_id,
        last_error="stale_error",
        consecutive_errors=4,
    )
    monkeypatch.setattr(
        "app.modules.scraper.service._run_coro_in_worker",
        _fake_run_coro(
            PoolScrapeResult(
                success=True,
                url="https://example.com/item",
                data=ExtractedProduct(title="Widget A", price=19.99, currency="USD"),
                scraper_layer="httpx",
            ),
        ),
    )
    monkeypatch.setattr(
        "app.modules.scraper.service._today_date_id",
        lambda _db: 20260401,
    )
    pool = MagicMock(spec=ScraperPool)
    svc = GlobalScrapeService(session, pool)
    res = svc.scrape_product(listing_id)
    assert res.success is True
    assert listing.last_error is None
    assert listing.consecutive_errors == 0

    added = [c.args[0] for c in session.add.call_args_list]
    assert any(isinstance(x, FactPrice) for x in added)
    fp = next(x for x in added if isinstance(x, FactPrice))
    assert float(fp.price) == pytest.approx(19.99)
    assert fp.in_stock is False
    assert product.name == "Widget A"
    assert session.commit.called


def test_scrape_product_price_not_found_partial(monkeypatch):
    """Pool reports price_not_found: no FactPrice, scrape_logs price_not_found, listing error counters."""
    listing_id = uuid.uuid4()
    product_id = uuid.uuid4()
    marketplace_id = uuid.uuid4()
    session, _product, listing = _build_mock_scrape_session(
        listing_id,
        product_id,
        marketplace_id,
        consecutive_errors=0,
    )
    monkeypatch.setattr(
        "app.modules.scraper.service._run_coro_in_worker",
        _fake_run_coro(
            PoolScrapeResult(
                success=False,
                url="https://example.com/item",
                error="price_not_found",
                data=None,
                scraper_layer="httpx",
            ),
        ),
    )
    pool = MagicMock(spec=ScraperPool)
    svc = GlobalScrapeService(session, pool)
    res = svc.scrape_product(listing_id)
    assert res.success is False
    assert listing.last_error == "price_not_found"
    assert listing.consecutive_errors == 1
    added = [c.args[0] for c in session.add.call_args_list]
    assert not any(isinstance(x, FactPrice) for x in added)
    slog = next(x for x in added if isinstance(x, ScrapeLog))
    assert slog.status == "price_not_found"


def test_scrape_product_missing_product_name_fallback_to_title(monkeypatch):
    """Only title (no product_name field): FactPrice + dim_product.name from title."""
    listing_id = uuid.uuid4()
    product_id = uuid.uuid4()
    marketplace_id = uuid.uuid4()
    session, product, listing = _build_mock_scrape_session(
        listing_id,
        product_id,
        marketplace_id,
    )
    monkeypatch.setattr(
        "app.modules.scraper.service._run_coro_in_worker",
        _fake_run_coro(
            PoolScrapeResult(
                success=True,
                url="https://example.com/item",
                data=ExtractedProduct(title="Title Only", price=10.0, currency="EUR"),
                scraper_layer="httpx",
            ),
        ),
    )
    monkeypatch.setattr(
        "app.modules.scraper.service._today_date_id",
        lambda _db: 20260401,
    )
    pool = MagicMock(spec=ScraperPool)
    svc = GlobalScrapeService(session, pool)
    res = svc.scrape_product(listing_id)
    assert res.success is True
    assert product.name == "Title Only"
    added = [c.args[0] for c in session.add.call_args_list]
    assert any(isinstance(x, FactPrice) for x in added)


def test_today_date_id_deadlock_safe():
    """SELECT → INSERT ON CONFLICT DO NOTHING → SELECT; second call uses first SELECT only."""
    import app.modules.scraper.service as svc

    from datetime import datetime as dt

    orig_dt = svc.datetime

    class FixedDateTime:
        @classmethod
        def now(cls, tz=None):
            return dt(2026, 4, 1, 12, 0, 0, tzinfo=tz or timezone.utc)

    svc.datetime = FixedDateTime  # type: ignore[misc]

    try:
        session = MagicMock()

        def make_result(val):
            m = MagicMock()
            m.scalar_one_or_none.return_value = val
            return m

        session.execute.side_effect = [
            make_result(None),
            make_result(None),
            make_result(20260401),
            make_result(20260401),
        ]
        assert _today_date_id(session) == 20260401
        assert _today_date_id(session) == 20260401
        assert session.execute.call_count == 4
    finally:
        svc.datetime = orig_dt


def test_fact_price_written_only_when_all_required_fields(monkeypatch):
    """Gate: name (or title), positive price, currency — otherwise no FactPrice row."""
    monkeypatch.setattr(
        "app.modules.scraper.service._today_date_id",
        lambda _db: 20260401,
    )

    cases: list[tuple[ExtractedProduct, bool]] = [
        (ExtractedProduct(title="Ok", price=5.0, currency="USD"), True),
        (ExtractedProduct(title="Ok", price=5.0, currency=None), False),
        (ExtractedProduct(title="Ok", price=5.0, currency=""), False),
        (ExtractedProduct(title="Ok", price=0.0, currency="USD"), False),
        (ExtractedProduct(title=None, price=5.0, currency="USD"), False),
    ]
    for payload, expect_fp in cases:
        lid = uuid.uuid4()
        pid = uuid.uuid4()
        mid = uuid.uuid4()
        session, _prod, _lst = _build_mock_scrape_session(lid, pid, mid)
        monkeypatch.setattr(
            "app.modules.scraper.service._run_coro_in_worker",
            _fake_run_coro(
                PoolScrapeResult(
                    success=True,
                    url="https://example.com/item",
                    data=payload,
                    scraper_layer="httpx",
                ),
            ),
        )
        svc = GlobalScrapeService(session, MagicMock(spec=ScraperPool))
        svc.scrape_product(lid)
        added = [c.args[0] for c in session.add.call_args_list]
        has_fp = any(isinstance(x, FactPrice) for x in added)
        assert has_fp is expect_fp, (payload, expect_fp)

    schema_path = Path(__file__).resolve().parents[2] / "alembic/versions/001_v2_schema.py"
    sql = schema_path.read_text(encoding="utf-8")
    assert "PARTITION BY RANGE (date_id)" in sql


# --- PostgreSQL integration (optional) ----------------------------------------


@pytest.mark.integration
def test_scrape_product_full_success_postgres(pg_session, monkeypatch):
    listing_id = _seed_listing(pg_session)
    _patch_commit_flush(pg_session)
    lst = pg_session.get(FactListing, listing_id)
    lst.last_error = "old"
    lst.consecutive_errors = 3

    monkeypatch.setattr(
        "app.modules.scraper.service._run_coro_in_worker",
        _fake_run_coro(
            PoolScrapeResult(
                success=True,
                url="https://example.com/p",
                data=ExtractedProduct(title="Widget A", price=19.99, currency="USD"),
                scraper_layer="httpx",
            ),
        ),
    )
    pool = MagicMock(spec=ScraperPool)
    svc = GlobalScrapeService(pg_session, pool)
    res = svc.scrape_product(listing_id)
    assert res.success is True
    pg_session.refresh(lst)
    assert lst.last_error is None
    assert lst.consecutive_errors == 0

    row = pg_session.scalars(
        select(FactPrice).where(FactPrice.listing_id == listing_id),
    ).first()
    assert row is not None


@pytest.mark.integration
def test_today_date_id_deadlock_safe_postgres(pg_session):
    a = _today_date_id(pg_session)
    b = _today_date_id(pg_session)
    assert a == b


@pytest.mark.integration
def test_fact_price_partition_child_postgres(pg_session):
    n = pg_session.execute(
        text(
            "SELECT COUNT(*) FROM pg_tables "
            "WHERE schemaname = 'public' AND tablename LIKE 'fact_price_%'",
        ),
    ).scalar_one()
    assert int(n) >= 1
