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


def _fake_browser_holder(mock_page):
    """Holder stub matching fetch_backends._shared_browser contract."""
    mock_ctx = MagicMock()
    mock_ctx.new_page = AsyncMock(return_value=mock_page)
    mock_ctx.close = AsyncMock()
    holder = MagicMock()
    holder.pages_served = 0
    holder.close = AsyncMock()
    holder.browser = MagicMock(new_context=AsyncMock(return_value=mock_ctx))
    return holder


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
async def test_layer_order_requires_js_renders_first(monkeypatch):
    pool = ScraperPool()
    monkeypatch.setattr(fb.settings, "proxy_provider_enabled", True)
    monkeypatch.setattr(fb.settings, "proxy_provider_username", "u")
    monkeypatch.setattr(fb.settings, "proxy_provider_password", "p")
    backends = pool._layer_order(requires_js=True)
    # access-mode policy: render hint puts the browser first and the paid
    # proxy backend never joins a non-proxy-mode order
    assert backends == [BackendId.BROWSER_RENDER, BackendId.DIRECT_HTTP]


@pytest.mark.asyncio
async def test_fetch_direct_http_404_and_403(monkeypatch):
    backend = DirectHttpBackend()

    client_403 = MagicMock(
        get=AsyncMock(
            return_value=MagicMock(status_code=403, text="", raise_for_status=lambda: None),
        ),
    )
    client_404 = MagicMock(
        get=AsyncMock(return_value=MagicMock(status_code=404, text="")),
    )

    monkeypatch.setattr(fb, "_shared_http_client", lambda: client_403)
    out, err = await backend.fetch("https://x.com")
    assert out is None and err == "blocked"

    monkeypatch.setattr(fb, "_shared_http_client", lambda: client_404)
    out2, err2 = await backend.fetch("https://x.com")
    assert out2 is None and err2 == "not_found"


@pytest.mark.asyncio
async def test_fetch_direct_http_timeout(monkeypatch):
    backend = DirectHttpBackend()
    import httpx

    client = MagicMock(get=AsyncMock(side_effect=httpx.TimeoutException("timeout")))
    monkeypatch.setattr(fb, "_shared_http_client", lambda: client)
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
    holder = _fake_browser_holder(mock_page)

    monkeypatch.setattr(fb, "_shared_browser", AsyncMock(return_value=holder))
    out, err = await backend.fetch("https://x.com/p")
    assert out is None and err == "blocked"


@pytest.mark.asyncio
async def test_browser_render_goto_timeout_message(monkeypatch):
    backend = BrowserRenderBackend()
    mock_page = MagicMock()
    mock_page.goto = AsyncMock(side_effect=Exception("navigation timeout exceeded"))
    holder = _fake_browser_holder(mock_page)

    monkeypatch.setattr(fb, "_shared_browser", AsyncMock(return_value=holder))
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
