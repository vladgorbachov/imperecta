"""Persistence tests: unit mocks (always) + optional PostgreSQL integration."""

from __future__ import annotations

import inspect
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from sqlalchemy import select, text

from app.models.app_tables import ScrapeLog
from app.models.dimensions import DimCountry, DimCurrency, DimMarketplace, DimProduct
from app.models.facts import FactListing, FactPrice
from app.modules.scraper.extractors import ExtractedProduct
from app.modules.scraper.scraper_pool import PoolScrapeResult, ScraperPool
from app.modules.scraper.service import GlobalScrapeService, _today_date_id


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
    """Transactional session; rollback after each test (no durable writes)."""
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
    """Minimal dim graph + fact_listing for scrape_product."""
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


def _patch_commit_flush(session) -> None:
    """Avoid committing outer transaction so rollback keeps the DB clean."""

    def _commit_flush() -> None:
        session.flush()

    session.commit = _commit_flush  # type: ignore[method-assign]


# --- Unit tests (no database) -------------------------------------------------


def test_today_date_id_idempotent_no_deadlock():
    """SELECT → INSERT ON CONFLICT DO NOTHING → SELECT; second call hits first SELECT only."""
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


def test_fact_price_partition_exists():
    """Migration defines RANGE partition on date_id and monthly child tables."""
    schema_path = Path(__file__).resolve().parents[1] / "alembic/versions/001_v2_schema.py"
    sql = schema_path.read_text(encoding="utf-8")
    assert "PARTITION BY RANGE (date_id)" in sql
    assert "CREATE TABLE fact_price_" in sql


def _build_mock_scrape_session(
    listing_id: uuid.UUID,
    product_id: uuid.UUID,
    marketplace_id: uuid.UUID,
) -> tuple[MagicMock, DimProduct, FactListing]:
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
    session.commit = MagicMock()
    session.rollback = MagicMock()
    return session, product, listing


def test_scrape_product_success_with_price(monkeypatch):
    """Title-only payload writes FactPrice, last_in_stock False, updates dim_product name."""
    listing_id = uuid.uuid4()
    product_id = uuid.uuid4()
    marketplace_id = uuid.uuid4()
    session, product, _listing = _build_mock_scrape_session(
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

    added = [c.args[0] for c in session.add.call_args_list]
    assert any(isinstance(x, FactPrice) for x in added)
    fp = next(x for x in added if isinstance(x, FactPrice))
    assert float(fp.price) == pytest.approx(19.99)
    assert fp.in_stock is False
    assert product.name == "Widget A"


def test_scrape_product_missing_product_name(monkeypatch):
    """No title and no product_name → no FactPrice row."""
    listing_id = uuid.uuid4()
    product_id = uuid.uuid4()
    marketplace_id = uuid.uuid4()
    session, _product, _listing = _build_mock_scrape_session(
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
                data=ExtractedProduct(title=None, price=None, currency=None),
                scraper_layer="httpx",
            ),
        ),
    )
    pool = MagicMock(spec=ScraperPool)
    svc = GlobalScrapeService(session, pool)
    res = svc.scrape_product(listing_id)
    assert res.success is True
    added = [c.args[0] for c in session.add.call_args_list]
    assert not any(isinstance(x, FactPrice) for x in added)


def test_scrape_product_price_not_found(monkeypatch):
    """Title present, price missing → scrape_logs price_not_found; no FactPrice."""
    listing_id = uuid.uuid4()
    product_id = uuid.uuid4()
    marketplace_id = uuid.uuid4()
    session, _product, _listing = _build_mock_scrape_session(
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
                data=ExtractedProduct(title="Has title", price=None, currency="USD"),
                scraper_layer="httpx",
            ),
        ),
    )
    pool = MagicMock(spec=ScraperPool)
    svc = GlobalScrapeService(session, pool)
    res = svc.scrape_product(listing_id)
    assert res.success is True
    added = [c.args[0] for c in session.add.call_args_list]
    assert not any(isinstance(x, FactPrice) for x in added)
    slog = next(x for x in added if isinstance(x, ScrapeLog))
    assert slog.status == "price_not_found"


# --- PostgreSQL integration (optional) ---------------------------------------


@pytest.mark.integration
def test_scrape_product_success_with_price_postgres(pg_session, monkeypatch):
    listing_id = _seed_listing(pg_session)
    _patch_commit_flush(pg_session)

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

    row = pg_session.scalars(
        select(FactPrice).where(FactPrice.listing_id == listing_id),
    ).first()
    assert row is not None
    assert float(row.price) == pytest.approx(19.99)
    assert row.in_stock is False

    prod = pg_session.get(
        DimProduct,
        pg_session.get(FactListing, listing_id).product_id,
    )
    assert prod.name == "Widget A"


@pytest.mark.integration
def test_scrape_product_missing_product_name_postgres(pg_session, monkeypatch):
    listing_id = _seed_listing(pg_session)
    _patch_commit_flush(pg_session)

    monkeypatch.setattr(
        "app.modules.scraper.service._run_coro_in_worker",
        _fake_run_coro(
            PoolScrapeResult(
                success=True,
                url="https://example.com/p",
                data=ExtractedProduct(title=None, price=None, currency=None),
                scraper_layer="httpx",
            ),
        ),
    )
    pool = MagicMock(spec=ScraperPool)
    svc = GlobalScrapeService(pg_session, pool)
    res = svc.scrape_product(listing_id)
    assert res.success is True

    row = pg_session.scalars(
        select(FactPrice).where(FactPrice.listing_id == listing_id),
    ).first()
    assert row is None


@pytest.mark.integration
def test_scrape_product_price_not_found_postgres(pg_session, monkeypatch):
    listing_id = _seed_listing(pg_session)
    _patch_commit_flush(pg_session)

    monkeypatch.setattr(
        "app.modules.scraper.service._run_coro_in_worker",
        _fake_run_coro(
            PoolScrapeResult(
                success=True,
                url="https://example.com/p",
                data=ExtractedProduct(title="Has title", price=None, currency="USD"),
                scraper_layer="httpx",
            ),
        ),
    )
    pool = MagicMock(spec=ScraperPool)
    svc = GlobalScrapeService(pg_session, pool)
    res = svc.scrape_product(listing_id)
    assert res.success is True

    row = pg_session.scalars(
        select(FactPrice).where(FactPrice.listing_id == listing_id),
    ).first()
    assert row is None

    slog = pg_session.scalars(
        select(ScrapeLog)
        .where(ScrapeLog.listing_id == listing_id)
        .order_by(ScrapeLog.id.desc())
        .limit(1),
    ).first()
    assert slog is not None
    assert slog.status == "price_not_found"


@pytest.mark.integration
def test_today_date_id_idempotent_no_deadlock_postgres(pg_session):
    a = _today_date_id(pg_session)
    b = _today_date_id(pg_session)
    assert a == b
    assert len(str(a)) == 8


@pytest.mark.integration
def test_fact_price_partition_exists_postgres(pg_session):
    n = pg_session.execute(
        text(
            "SELECT COUNT(*) FROM pg_tables "
            "WHERE schemaname = 'public' AND tablename LIKE 'fact_price_%'",
        ),
    ).scalar_one()
    assert int(n) >= 1
