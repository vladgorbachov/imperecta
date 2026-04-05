"""Unit tests for ScraperPool: layers, PoolScrapeResult shape, quality gates."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

import app.modules.scraper.scraper_pool as sp
from app.modules.scraper.scraper_pool import MAX_VALID_PRICE, ScraperPool


@pytest.mark.asyncio
async def test_scrape_product_logs_each_layer(monkeypatch, caplog):
    """Each transport attempt is logged with duration (even when HTML is empty)."""
    caplog.set_level("INFO")
    pool = ScraperPool()
    calls: list[str] = []

    async def fake_layer(layer: str, url: str):
        calls.append(layer)
        return None, "timeout"

    monkeypatch.setattr(pool, "_fetch_layer_with_retries", fake_layer)
    r = await pool.scrape_product("https://example.com/p/1")
    assert not r.success
    assert any("scrape_layer" in m for m in caplog.messages)
    assert calls  # at least one layer tried


@pytest.mark.asyncio
async def test_pool_result_has_extracted_and_missing_fields(monkeypatch):
    pool = ScraperPool()
    html = """
    <html><head><script type="application/ld+json">
    {"@type":"Product","name":"Item","offers":{"price":"12.5","priceCurrency":"USD"}}
    </script></head><body></body></html>
    """

    async def fake_layer(layer: str, url: str):
        return html, None

    monkeypatch.setattr(pool, "_fetch_layer_with_retries", fake_layer)
    r = await pool.scrape_product("https://shop.example/p/x")
    assert r.success and r.data
    assert "title" in r.extracted_fields
    assert "price" in r.extracted_fields
    assert isinstance(r.missing_fields, list)


@pytest.mark.asyncio
async def test_raw_html_only_when_decodo_disabled(monkeypatch):
    pool = ScraperPool()
    html = "<html><head><title>T</title><script type=\"application/ld+json\">"
    html += '{"@type":"Product","name":"N","offers":{"price":"1","priceCurrency":"USD"}}'
    html += "</script></head></html>"

    async def fake_layer(layer: str, url: str):
        return html, None

    monkeypatch.setattr(pool, "_fetch_layer_with_retries", fake_layer)
    monkeypatch.setattr(sp.settings, "decodo_enabled", False)
    r = await pool.scrape_product("https://example.com/p")
    assert r.success
    assert r.raw_html is not None and "Product" in r.raw_html

    monkeypatch.setattr(sp.settings, "decodo_enabled", True)
    monkeypatch.setattr(sp.settings, "decodo_username", "u")
    monkeypatch.setattr(sp.settings, "decodo_password", "p")
    r2 = await pool.scrape_product("https://example.com/p")
    assert r2.success
    assert r2.raw_html is None


@pytest.mark.asyncio
async def test_price_at_max_boundary_ok(monkeypatch):
    pool = ScraperPool()
    price_str = f"{MAX_VALID_PRICE:.2f}"
    html = f"""
    <script type="application/ld+json">
    {{"@type":"Product","name":"P","offers":{{"price":"{price_str}","priceCurrency":"USD"}}}}
    </script>
    """

    async def fake_layer(layer: str, url: str):
        return html, None

    monkeypatch.setattr(pool, "_fetch_layer_with_retries", fake_layer)
    r = await pool.scrape_product("https://x.com/p")
    assert r.success and r.data and r.data.price == pytest.approx(MAX_VALID_PRICE)
