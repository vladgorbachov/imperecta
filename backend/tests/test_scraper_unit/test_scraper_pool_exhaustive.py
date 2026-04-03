"""Deep unit tests for ScraperPool (HTTP mocked at layer boundary; no fake listings)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import app.modules.scraper.scraper_pool as sp
from app.modules.scraper.scraper_pool import ScraperPool


@pytest.mark.asyncio
async def test_scrape_product_success_after_httpx_html(monkeypatch):
    pool = ScraperPool()
    html = """
    <html><head><script type="application/ld+json">
    {"@type":"Product","name":"X","offers":{"price":"10","priceCurrency":"USD"}}
    </script></head><body><h1>X</h1></body></html>
    """

    async def fake_layer(layer: str, url: str):
        return html, None

    monkeypatch.setattr(pool, "_fetch_layer_with_retries", fake_layer)
    r = await pool.scrape_product("https://shop.example/p/1")
    assert r.success and r.data and r.data.price == 10.0


@pytest.mark.asyncio
async def test_scrape_product_parse_error_in_extract(monkeypatch):
    pool = ScraperPool()

    async def fake_layer(layer: str, url: str):
        return "<html>not valid for merge</html>", None

    def boom(*_a, **_k):
        raise ValueError("parse")

    monkeypatch.setattr(pool, "_fetch_layer_with_retries", fake_layer)
    monkeypatch.setattr(sp, "merge_results", boom)
    r = await pool.scrape_product("https://shop.example/p/2")
    assert not r.success and "parse_error" in (r.error or "")


@pytest.mark.asyncio
async def test_scrape_product_price_overflow_discarded(monkeypatch):
    pool = ScraperPool()
    html = """
    <script type="application/ld+json">
    {"@type":"Product","name":"P","offers":{"price":"99999999999999","priceCurrency":"USD"}}
    </script>
    """

    async def fake_layer(layer: str, url: str):
        return html, None

    monkeypatch.setattr(pool, "_fetch_layer_with_retries", fake_layer)
    r = await pool.scrape_product("https://x.com/p")
    assert not r.success and r.error == "price_not_found"


@pytest.mark.asyncio
async def test_fetch_html_decodo_paths(monkeypatch):
    pool = ScraperPool()
    monkeypatch.setattr(sp.settings, "decodo_enabled", True)
    monkeypatch.setattr(sp.settings, "decodo_username", "u")
    monkeypatch.setattr(sp.settings, "decodo_password", "p")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"results": [{"content": "<html>ok</html>"}]}

    class CM:
        async def __aenter__(self):
            return MagicMock(post=AsyncMock(return_value=mock_resp))

        async def __aexit__(self, *a):
            return None

    monkeypatch.setattr(sp.httpx, "AsyncClient", lambda **k: CM())
    out, err = await pool._fetch_html_decodo("https://example.com")
    assert out == "<html>ok</html>" and err is None


@pytest.mark.asyncio
async def test_listing_scrape_result_and_fetch_html_none(monkeypatch):
    pool = ScraperPool()

    async def nope(layer: str, url: str):
        return None, "timeout:httpx"

    monkeypatch.setattr(pool, "_fetch_layer_with_retries", nope)
    assert await pool.fetch_html("https://x.com") is None
    lr = await pool.scrape_listing("https://x.com/cat")
    assert not lr.success


@pytest.mark.asyncio
async def test_map_layer_error_variants():
    pool = ScraperPool()
    assert "timeout" in pool._map_layer_error("timeout", "httpx")
    assert "fetch_failed" in pool._map_layer_error("fetch_failed", "httpx")


@pytest.mark.asyncio
async def test_playwright_fetch_404_branch(monkeypatch):
    pool = ScraperPool()
    mock_page = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status = 404
    mock_page.goto = AsyncMock(return_value=mock_resp)
    mock_page.wait_for_timeout = AsyncMock()
    mock_page.content = AsyncMock(return_value="<html></html>")
    mock_browser = MagicMock()
    mock_browser.close = AsyncMock()
    mock_ctx = MagicMock()
    mock_ctx.new_page = AsyncMock(return_value=mock_page)
    mock_browser.new_context = AsyncMock(return_value=mock_ctx)

    class PW:
        async def __aenter__(self):
            return MagicMock(chromium=MagicMock(launch=AsyncMock(return_value=mock_browser)))

        async def __aexit__(self, *a):
            return None

    monkeypatch.setattr(sp, "async_playwright", lambda: PW())
    out, err = await pool._fetch_html_playwright("https://x.com/p")
    assert out is None and err == "not_found"
