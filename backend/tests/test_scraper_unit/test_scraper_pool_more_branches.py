"""Additional ScraperPool branch coverage (fetch backends, listing crawl)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

import app.modules.scraper.fetch_backends as fb
from app.modules.scraper.fetch_backends import (
    BackendId,
    BrowserRenderBackend,
    DirectHttpBackend,
    ProxyProviderBackend,
)
from app.modules.scraper.scraper_pool import ScraperPool


@pytest.mark.asyncio
async def test_scrape_listing_success_with_product_links(monkeypatch):
    pool = ScraperPool()
    html = """
    <html><body>
    <a href="https://shop.example/p/one">one</a>
    </body></html>
    """

    async def fake_layer(backend_id: BackendId, url: str, **kwargs):
        return html, None

    monkeypatch.setattr(pool, "_fetch_layer_with_retries", fake_layer)
    r = await pool.scrape_listing("https://shop.example/category")
    assert r.success and len(r.product_urls) >= 1


@pytest.mark.asyncio
async def test_fetch_html_returns_first_html(monkeypatch):
    pool = ScraperPool()

    async def fake_layer(backend_id: BackendId, url: str, **kwargs):
        return "<html>ok</html>", None

    monkeypatch.setattr(pool, "_fetch_layer_with_retries", fake_layer)
    assert await pool.fetch_html("https://x.com") == "<html>ok</html>"


@pytest.mark.asyncio
async def test_layer_order_requires_js_inserts_browser_render(monkeypatch):
    pool = ScraperPool()
    monkeypatch.setattr(fb.settings, "proxy_provider_enabled", True)
    monkeypatch.setattr(fb.settings, "proxy_provider_username", "u")
    monkeypatch.setattr(fb.settings, "proxy_provider_password", "p")
    backends = pool._layer_order(requires_js=True)
    assert backends[1] == BackendId.BROWSER_RENDER


@pytest.mark.asyncio
async def test_fetch_direct_http_404_and_403(monkeypatch):
    backend = DirectHttpBackend()

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

    monkeypatch.setattr(fb.httpx, "AsyncClient", lambda **k: CM403())
    out, err = await backend.fetch("https://x.com")
    assert out is None and err == "blocked"

    monkeypatch.setattr(fb.httpx, "AsyncClient", lambda **k: CM404())
    out2, err2 = await backend.fetch("https://x.com")
    assert out2 is None and err2 == "not_found"


@pytest.mark.asyncio
async def test_fetch_direct_http_timeout(monkeypatch):
    backend = DirectHttpBackend()
    import httpx

    class CM:
        async def __aenter__(self):
            return MagicMock(
                get=AsyncMock(side_effect=httpx.TimeoutException("timeout")),
            )

        async def __aexit__(self, *a):
            return None

    monkeypatch.setattr(fb.httpx, "AsyncClient", lambda **k: CM())
    out, err = await backend.fetch("https://x.com")
    assert out is None and err == "timeout"


@pytest.mark.asyncio
async def test_fetch_proxy_provider_404(monkeypatch):
    backend = ProxyProviderBackend()
    monkeypatch.setattr(fb.settings, "proxy_provider_enabled", True)
    monkeypatch.setattr(fb.settings, "proxy_provider_username", "u")
    monkeypatch.setattr(fb.settings, "proxy_provider_password", "p")
    monkeypatch.setattr(
        fb,
        "acquire_proxy_provider_token",
        AsyncMock(return_value=True),
    )

    mock_resp = MagicMock()
    mock_resp.status_code = 404

    class CM:
        async def __aenter__(self):
            return MagicMock(post=AsyncMock(return_value=mock_resp))

        async def __aexit__(self, *a):
            return None

    monkeypatch.setattr(fb.httpx, "AsyncClient", lambda **k: CM())
    out, err = await backend.fetch("https://x.com")
    assert out is None and err == "not_found"


@pytest.mark.asyncio
async def test_browser_render_fetch_403(monkeypatch):
    backend = BrowserRenderBackend()
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

    monkeypatch.setattr(fb, "async_playwright", lambda: PW())
    out, err = await backend.fetch("https://x.com/p")
    assert out is None and err == "blocked"


@pytest.mark.asyncio
async def test_browser_render_goto_timeout_message(monkeypatch):
    backend = BrowserRenderBackend()
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

    monkeypatch.setattr(fb, "async_playwright", lambda: PW())
    out, err = await backend.fetch("https://x.com/p")
    assert out is None and err == "timeout"


@pytest.mark.asyncio
async def test_fetch_layer_retries_backoff(monkeypatch):
    import app.modules.scraper.scraper_pool as sp

    pool = ScraperPool()
    calls = {"n": 0}

    async def slow(backend_id: BackendId, url: str, **kwargs):
        calls["n"] += 1
        return None, "fetch_failed"

    monkeypatch.setattr(pool, "_fetch_by_backend_once", slow)
    monkeypatch.setattr(sp.asyncio, "sleep", AsyncMock())
    out, err = await pool._fetch_layer_with_retries(BackendId.DIRECT_HTTP, "https://x.com")
    assert out is None
    assert calls["n"] == sp.FETCH_ATTEMPTS_PER_LAYER
