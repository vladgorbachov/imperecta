"""Additional ScraperPool branch coverage (fetch layers, listing crawl)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

import app.modules.scraper.scraper_pool as sp
from app.modules.scraper.scraper_pool import ScraperPool


@pytest.mark.asyncio
async def test_scrape_listing_success_with_product_links(monkeypatch):
    pool = ScraperPool()
    html = """
    <html><body>
    <a href="https://shop.example/p/one">one</a>
    </body></html>
    """

    async def fake_layer(layer: str, url: str):
        return html, None

    monkeypatch.setattr(pool, "_fetch_layer_with_retries", fake_layer)
    r = await pool.scrape_listing("https://shop.example/category")
    assert r.success and len(r.product_urls) >= 1


@pytest.mark.asyncio
async def test_fetch_html_returns_first_html(monkeypatch):
    pool = ScraperPool()

    async def fake_layer(layer: str, url: str):
        return "<html>ok</html>", None

    monkeypatch.setattr(pool, "_fetch_layer_with_retries", fake_layer)
    assert await pool.fetch_html("https://x.com") == "<html>ok</html>"


@pytest.mark.asyncio
async def test_layer_order_requires_js_inserts_playwright(monkeypatch):
    pool = ScraperPool()
    monkeypatch.setattr(sp.settings, "decodo_enabled", True)
    monkeypatch.setattr(sp.settings, "decodo_username", "u")
    monkeypatch.setattr(sp.settings, "decodo_password", "p")
    layers = pool._layer_order(requires_js=True)
    assert layers[1] == "playwright"


@pytest.mark.asyncio
async def test_fetch_httpx_404_and_403(monkeypatch):
    pool = ScraperPool()

    class CM403:
        async def __aenter__(self):
            return MagicMock(
                get=AsyncMock(
                    return_value=MagicMock(status_code=403, text="", raise_for_status=lambda: None),
                ),
            )

        async def __aexit__(self, *a):
            return None

    class CM404:
        async def __aenter__(self):
            return MagicMock(
                get=AsyncMock(
                    return_value=MagicMock(status_code=404, text=""),
                ),
            )

        async def __aexit__(self, *a):
            return None

    monkeypatch.setattr(sp.httpx, "AsyncClient", lambda **k: CM403())
    out, err = await pool._fetch_html_httpx("https://x.com")
    assert out is None and err == "blocked"

    monkeypatch.setattr(sp.httpx, "AsyncClient", lambda **k: CM404())
    out2, err2 = await pool._fetch_html_httpx("https://x.com")
    assert out2 is None and err2 == "not_found"


@pytest.mark.asyncio
async def test_fetch_httpx_timeout(monkeypatch):
    pool = ScraperPool()
    import httpx

    class CM:
        async def __aenter__(self):
            return MagicMock(
                get=AsyncMock(side_effect=httpx.TimeoutException("timeout")),
            )

        async def __aexit__(self, *a):
            return None

    monkeypatch.setattr(sp.httpx, "AsyncClient", lambda **k: CM())
    out, err = await pool._fetch_html_httpx("https://x.com")
    assert out is None and err == "timeout"


@pytest.mark.asyncio
async def test_fetch_decodo_404(monkeypatch):
    pool = ScraperPool()
    monkeypatch.setattr(sp.settings, "decodo_enabled", True)
    monkeypatch.setattr(sp.settings, "decodo_username", "u")
    monkeypatch.setattr(sp.settings, "decodo_password", "p")

    mock_resp = MagicMock()
    mock_resp.status_code = 404

    class CM:
        async def __aenter__(self):
            return MagicMock(post=AsyncMock(return_value=mock_resp))

        async def __aexit__(self, *a):
            return None

    monkeypatch.setattr(sp.httpx, "AsyncClient", lambda **k: CM())
    out, err = await pool._fetch_html_decodo("https://x.com")
    assert out is None and err == "not_found"


@pytest.mark.asyncio
async def test_playwright_fetch_403(monkeypatch):
    pool = ScraperPool()
    mock_page = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status = 403
    mock_page.goto = AsyncMock(return_value=mock_resp)
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
    assert out is None and err == "blocked"


@pytest.mark.asyncio
async def test_playwright_goto_timeout_message(monkeypatch):
    pool = ScraperPool()
    mock_page = MagicMock()
    mock_page.goto = AsyncMock(side_effect=Exception("navigation timeout exceeded"))
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
    assert out is None and err == "timeout"


@pytest.mark.asyncio
async def test_fetch_layer_retries_backoff(monkeypatch):
    pool = ScraperPool()
    calls = {"n": 0}

    async def slow(layer: str, url: str):
        calls["n"] += 1
        return None, "fetch_failed"

    monkeypatch.setattr(pool, "_fetch_by_layer_once", slow)
    monkeypatch.setattr(sp.asyncio, "sleep", AsyncMock())
    out, err = await pool._fetch_layer_with_retries("httpx", "https://x.com")
    assert out is None
    assert calls["n"] == sp.FETCH_ATTEMPTS_PER_LAYER
