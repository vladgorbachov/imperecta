"""Tests for COLLECTOR-GATE-AND-LOCALE: structural pool gate + locale chain."""

from __future__ import annotations

import asyncio
import re
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from bs4 import BeautifulSoup

import app.modules.scraper.discovery as disc
from app.modules.discovery.gate_persist import PoolWriteResult, write_pool_dtos_sync
from app.models.dimensions import DimMarketplace
from app.models.facts import FactListing
from app.modules.data_firewall.firewall import evaluate_ecommerce
from app.modules.scraper.extractors import parse_sitemap_xml
from app.modules.scraper.fetch_backends import DirectHttpBackend
from app.modules.scraper.locale_selection import (
    build_accept_language_header,
    select_locale_url,
)
from app.modules.scraper.scraper_pool import PoolScrapeResult
from app.modules.scraper.service import GlobalScrapeService

BACKEND_ROOT = Path(__file__).resolve().parents[1]
MIGRATION_028 = BACKEND_ROOT / "alembic/versions/028_add_fact_listing_page_role.py"


def _patch_pool_write(monkeypatch) -> dict:
    """Capture pool DTO batches handed to asyncio.to_thread (gate write bridge)."""
    state: dict = {"batches": [], "calls": 0}

    async def fake_to_thread(func, dtos):
        state["calls"] += 1
        state["batches"].append(list(dtos))
        assert func is write_pool_dtos_sync
        return PoolWriteResult(inserted=len(dtos), rejected=0)

    monkeypatch.setattr(asyncio, "to_thread", fake_to_thread)
    return state


_EXECUTE_STRING_RE = re.compile(
    r'op\.execute\(\s*(?:r?"""(.*?)"""|r?\'\'\'(.*?)\'\'\'|"([^"]*)"|\'([^\']*)\')',
    re.DOTALL,
)


def _migration_execute_strings(path: Path) -> list[str]:
    source = path.read_text(encoding="utf-8")
    strings: list[str] = []
    for match in _EXECUTE_STRING_RE.finditer(source):
        value = next(group for group in match.groups() if group is not None)
        strings.append(value)
    return strings


def _count_sql_statements(sql: str) -> int:
    return len([part for part in sql.split(";") if part.strip()])


def test_migration_028_has_no_multi_statement_op_execute_literals() -> None:
    offenders: list[str] = []
    for sql in _migration_execute_strings(MIGRATION_028):
        if _count_sql_statements(sql) > 1:
            offenders.append(sql.strip()[:120])
    assert offenders == [], f"multi-statement op.execute literals: {offenders}"


def test_select_locale_url_chain() -> None:
    alternates = {
        "fi": "https://shop.example/fi/p/1",
        "en": "https://shop.example/en/p/1",
        "x-default": "https://shop.example/p/1",
    }
    assert select_locale_url("https://shop.example/fi/p/1", alternates, "fi") == (
        "https://shop.example/en/p/1"
    )
    no_en = {"fi": "https://shop.example/fi/p/1", "x-default": "https://shop.example/p/1"}
    assert select_locale_url("https://shop.example/fi/p/1", no_en, "fi") == (
        "https://shop.example/fi/p/1"
    )
    only_default = {"x-default": "https://shop.example/p/1"}
    assert select_locale_url("https://shop.example/fi/p/1", only_default, "de") == (
        "https://shop.example/p/1"
    )


def test_sitemap_parses_hreflang_alternates() -> None:
    xml = """<?xml version="1.0" encoding="UTF-8"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
            xmlns:xhtml="http://www.w3.org/1999/xhtml">
      <url>
        <loc>https://shop.example/fi/p/1</loc>
        <xhtml:link rel="alternate" hreflang="fi"
          href="https://shop.example/fi/p/1"/>
        <xhtml:link rel="alternate" hreflang="en"
          href="https://shop.example/en/p/1"/>
        <xhtml:link rel="alternate" hreflang="x-default"
          href="https://shop.example/p/1"/>
      </url>
    </urlset>
    """
    parsed = parse_sitemap_xml(xml, "https://shop.example")
    entries = parsed["url_entries"]
    assert len(entries) == 1
    alternates = entries[0]["alternates"]
    assert alternates["en"] == "https://shop.example/en/p/1"
    assert alternates["x-default"] == "https://shop.example/p/1"


@pytest.mark.asyncio
async def test_fetch_sends_accept_language() -> None:
    backend = DirectHttpBackend()
    captured: dict[str, object] = {}

    class _FakeResponse:
        status_code = 200
        text = "<html></html>"

    class _FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, url, headers=None):
            captured["headers"] = headers
            return _FakeResponse()

    import httpx

    original_client = httpx.AsyncClient
    httpx.AsyncClient = lambda **kwargs: _FakeClient()  # type: ignore[misc, assignment]
    try:
        html, err = await backend.fetch(
            "https://shop.example/p/1",
            accept_language="en, fi;q=0.8",
        )
    finally:
        httpx.AsyncClient = original_client  # type: ignore[misc, assignment]

    assert err is None
    assert html is not None
    headers = captured.get("headers") or {}
    assert headers.get("Accept-Language") == "en, fi;q=0.8"


@pytest.mark.asyncio
async def test_discovery_gate_rejects_nonproduct() -> None:
    crawler = disc.DiscoveryCrawler(MagicMock(), MagicMock())
    urls = [
        "https://shop.example/p/1",
        "https://shop.example/collections/all",
        "https://shop.example/p/2",
    ]

    async def classify_side_effect(url: str, **kwargs):
        if "/collections/" in url:
            return "listing", url
        return "product", url

    crawler._classify_and_resolve_url = AsyncMock(side_effect=classify_side_effect)
    accepted, stats = await crawler._filter_urls_by_role(urls, marketplace_locale="fi")
    assert stats["mode"] == "full"
    assert len(accepted) == 2
    assert all("/p/" in u for u in accepted)


@pytest.mark.asyncio
async def test_discovery_no_trust_sample_blind_accept(monkeypatch) -> None:
    crawler = disc.DiscoveryCrawler(MagicMock(), MagicMock())
    urls = [f"https://shop.example/p/{index}" for index in range(150)]
    calls: list[str] = []

    async def classify_side_effect(url: str, **kwargs):
        calls.append(url)
        if url.endswith("/p/0"):
            return "listing", url
        return "product", url

    crawler._classify_and_resolve_url = AsyncMock(side_effect=classify_side_effect)
    monkeypatch.setattr(disc.random, "sample", lambda population, k: population[:k])
    accepted, stats = await crawler._filter_urls_by_role(urls, marketplace_locale=None)
    assert stats["mode"] == "full_large"
    assert len(calls) == 150
    assert len(accepted) == 149


@pytest.mark.asyncio
async def test_save_product_urls_sets_page_role(monkeypatch) -> None:
    mp_id = uuid4()
    db = AsyncMock()
    existing = MagicMock()
    existing.all.return_value = []
    db.execute = AsyncMock(return_value=existing)
    db.add = MagicMock()
    db.commit = AsyncMock()
    pool_state = _patch_pool_write(monkeypatch)

    crawler = disc.DiscoveryCrawler(db, MagicMock())
    await crawler._save_product_urls(mp_id, ["https://shop.example/p/abc-12345"])

    assert pool_state["calls"] == 1
    assert len(pool_state["batches"][0]) == 1
    assert pool_state["batches"][0][0].fact_listing["page_role"] == "product"


def test_scrape_prunes_nonproduct() -> None:
    db = MagicMock()
    listing_id = uuid4()
    product_id = uuid4()
    listing = FactListing(
        id=listing_id,
        product_id=product_id,
        marketplace_id=uuid4(),
        external_url="https://shop.example/collections/all",
        is_active=True,
    )
    product = MagicMock()
    product.id = product_id
    db.get.return_value = product
    count_result = MagicMock()
    count_result.scalar.return_value = 0
    db.execute.return_value = count_result

    svc = GlobalScrapeService(db, MagicMock())
    svc._persist_scrape_log = MagicMock(return_value=True)
    from app.modules.scraper.extractors import ExtractedProduct

    result = PoolScrapeResult(
        success=False,
        url=listing.external_url,
        error="price_not_found",
        data=ExtractedProduct(page_role="hub"),
        page_role="hub",
    )
    out = svc._persist_scrape_pool_result(listing_id, listing, result, now=MagicMock())
    assert out.log_status == "not_a_product"
    db.delete.assert_any_call(listing)
    db.delete.assert_any_call(product)


def test_scrape_does_not_prune_transient_price_not_found() -> None:
    db = MagicMock()
    listing_id = uuid4()
    listing = FactListing(
        id=listing_id,
        product_id=uuid4(),
        marketplace_id=uuid4(),
        external_url="https://shop.example/p/real",
        is_active=True,
    )
    svc = GlobalScrapeService(db, MagicMock())
    result = PoolScrapeResult(
        success=False,
        url=listing.external_url,
        error="price_not_found",
        data=None,
        page_role=None,
    )
    svc._persist_listing_housekeeping_or_fail = MagicMock(return_value=None)
    svc._persist_scrape_log = MagicMock(return_value=True)
    svc._determine_log_status = MagicMock(return_value="price_not_found")
    svc._persist_scrape_pool_result(listing_id, listing, result, now=MagicMock())
    db.delete.assert_not_called()


def test_firewall_rejects_nonproduct() -> None:
    class _FakeData:
        product_name = "Widget"
        title = "Widget"
        price = 10.0
        currency = "EUR"
        currency_raw = "EUR"
        page_role = "listing"

    class _Resolver:
        def matches(self, marketplace_id, currency):
            return True

    outcome = evaluate_ecommerce(
        _FakeData(),
        marketplace_id=uuid4(),
        currency_resolver=_Resolver(),
        page_role="listing",
        db=None,
    )
    assert outcome.passed is False
    assert outcome.reject_reason == "not_a_product"


def test_build_accept_language_header() -> None:
    assert "en" in build_accept_language_header(None)
    header = build_accept_language_header("fi")
    assert header.startswith("en")
    assert "fi" in header
