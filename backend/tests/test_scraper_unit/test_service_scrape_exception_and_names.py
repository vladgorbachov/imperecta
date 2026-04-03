"""GlobalScrapeService: pool exception path and product name placeholder updates."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from unittest.mock import MagicMock

import inspect

import pytest

from app.models.dimensions import DimMarketplace, DimProduct
from app.models.facts import FactListing
from app.modules.scraper.extractors import ExtractedProduct
from app.modules.scraper.scraper_pool import PoolScrapeResult, ScraperPool
from app.modules.scraper.service import GlobalScrapeService
from fixtures.scraper_fixtures import _fake_run_coro


def test_scrape_product_pool_raises_exception(monkeypatch):
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
    product = DimProduct(id=product_id, name="product", name_normalized="product")
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
    session.commit = MagicMock()

    def boom(coro):
        if inspect.iscoroutine(coro):
            coro.close()
        raise RuntimeError("io")

    monkeypatch.setattr("app.modules.scraper.service._run_coro_in_worker", boom)

    svc = GlobalScrapeService(session, MagicMock(spec=ScraperPool))
    r = svc.scrape_product(listing_id)
    assert r.success is False and "exception" in (r.error or "").lower()


def test_product_name_replace_placeholder_and_title_only(monkeypatch):
    listing_id = uuid.uuid4()
    product_id = uuid.uuid4()
    marketplace_id = uuid.uuid4()
    listing = FactListing(
        id=listing_id,
        product_id=product_id,
        marketplace_id=marketplace_id,
        external_url="https://example.com/path/item-slug",
        url_hash=FactListing.compute_url_hash("https://example.com/path/item-slug"),
    )
    product = DimProduct(id=product_id, name="product", name_normalized="product")
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
    session.commit = MagicMock()
    monkeypatch.setattr("app.modules.scraper.service._today_date_id", lambda _db: 20260101)

    data_no_pn = ExtractedProduct(title="OnlyTitle", price=10.0, currency="USD")
    monkeypatch.setattr(
        "app.modules.scraper.service._run_coro_in_worker",
        _fake_run_coro(
            PoolScrapeResult(success=True, url=listing.external_url, data=data_no_pn),
        ),
    )

    svc = GlobalScrapeService(session, MagicMock(spec=ScraperPool))
    svc.scrape_product(listing_id)
    assert product.name != "product" or product.name_normalized != "product"


def test_determine_product_name_field_missing_price(monkeypatch):
    from dataclasses import dataclass

    @dataclass
    class P:
        product_name: str | None = None
        title: str | None = "T"
        price: float | None = None
        currency: str | None = "USD"

    svc = GlobalScrapeService(MagicMock(), MagicMock())
    payload = P(product_name="X", title="T", price=None, currency="USD")
    r = PoolScrapeResult(success=True, url="u", data=payload)
    assert svc._determine_log_status(r, data=payload) == "price_not_found"


@dataclass
class _PayloadWithProductName:
    product_name: str
    title: str | None = None
    price: float = 10.0
    currency: str = "USD"
    image_url: str | None = None
    original_price: float | None = None


def test_product_name_nonempty_updates_dim_product(monkeypatch):
    listing_id = uuid.uuid4()
    product_id = uuid.uuid4()
    marketplace_id = uuid.uuid4()
    listing = FactListing(
        id=listing_id,
        product_id=product_id,
        marketplace_id=marketplace_id,
        external_url="https://example.com/item",
        url_hash=FactListing.compute_url_hash("https://example.com/item"),
    )
    product = DimProduct(id=product_id, name="product", name_normalized="product")
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
    session.commit = MagicMock()
    monkeypatch.setattr("app.modules.scraper.service._today_date_id", lambda _db: 20260101)

    payload = _PayloadWithProductName(
        product_name="Scraped Name",
        image_url="https://cdn.example/img.png",
    )
    monkeypatch.setattr(
        "app.modules.scraper.service._run_coro_in_worker",
        _fake_run_coro(
            PoolScrapeResult(success=True, url=listing.external_url, data=payload),
        ),
    )

    svc = GlobalScrapeService(session, MagicMock(spec=ScraperPool))
    svc.scrape_product(listing_id)
    assert product.name == "Scraped Name"
    assert product.image_url == "https://cdn.example/img.png"


def test_find_incomplete_products_mock():
    session = MagicMock()
    session.execute.return_value.all.return_value = [(uuid.uuid4(),)]
    svc = GlobalScrapeService(session, MagicMock(spec=ScraperPool))
    assert len(svc.find_incomplete_products(5)) == 1
