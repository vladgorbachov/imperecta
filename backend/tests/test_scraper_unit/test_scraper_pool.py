"""Unit tests for ScraperPool: layers, PoolScrapeResult shape, quality gates."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

import app.modules.scraper.fetch_backends as fb
import app.modules.scraper.scraper_pool as sp
from app.modules.scraper.fetch_backends import BackendId, ProxyProviderBackend
from app.modules.scraper.scraper_pool import ScraperPool


@pytest.mark.asyncio
async def test_scrape_product_logs_each_layer(monkeypatch, caplog):
    """Each transport attempt is logged with duration (even when HTML is empty)."""
    caplog.set_level("INFO")
    pool = ScraperPool()
    calls: list[BackendId] = []

    async def fake_layer(backend_id: BackendId, url: str, **kwargs):
        calls.append(backend_id)
        return None, "timeout"

    monkeypatch.setattr(pool, "_fetch_layer_with_retries", fake_layer)
    r = await pool.scrape_product("https://example.com/p/1")
    assert not r.success
    assert any("scrape_backend" in m or "fetch_backend_attempt" in m for m in caplog.messages)
    assert calls


@pytest.mark.asyncio
async def test_pool_result_has_extracted_and_missing_fields(monkeypatch):
    pool = ScraperPool()
    html = """
    <html><head><script type="application/ld+json">
    {"@type":"Product","name":"Item","offers":{"price":"12.5","priceCurrency":"USD"}}
    </script></head><body></body></html>
    """

    async def fake_layer(backend_id: BackendId, url: str, **kwargs):
        return html, None

    monkeypatch.setattr(pool, "_fetch_layer_with_retries", fake_layer)
    r = await pool.scrape_product("https://shop.example/p/x")
    assert r.success and r.data
    assert "title" in r.extracted_fields
    assert "price" in r.extracted_fields
    assert isinstance(r.missing_fields, list)


@pytest.mark.asyncio
async def test_raw_html_only_when_proxy_provider_disabled(monkeypatch):
    pool = ScraperPool()
    html = "<html><head><title>T</title><script type=\"application/ld+json\">"
    html += '{"@type":"Product","name":"N","offers":{"price":"1","priceCurrency":"USD"}}'
    html += "</script></head></html>"

    async def fake_layer(backend_id: BackendId, url: str, **kwargs):
        return html, None

    monkeypatch.setattr(pool, "_fetch_layer_with_retries", fake_layer)
    monkeypatch.setattr(ProxyProviderBackend, "is_enabled", staticmethod(lambda: False))
    r = await pool.scrape_product("https://example.com/p")
    assert r.success
    assert r.raw_html is not None and "Product" in r.raw_html

    monkeypatch.setattr(ProxyProviderBackend, "is_enabled", staticmethod(lambda: True))
    monkeypatch.setattr(ProxyProviderBackend, "is_configured", staticmethod(lambda: True))
    with patch.object(
        fb.ProxyProviderBackend,
        "fetch",
        AsyncMock(return_value=("<html/>", None)),
    ):
        r2 = await pool.scrape_product("https://example.com/p")
    assert r2.success
    assert r2.raw_html is None
