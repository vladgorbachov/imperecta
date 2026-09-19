"""Unit tests for ScraperPool fetch retries (no real HTTP)."""

import pytest
from unittest.mock import AsyncMock

from app.modules.scraper.fetch_backends import BackendId
from app.modules.scraper.scraper_pool import ScraperPool


@pytest.mark.asyncio
async def test_fetch_layer_retries_until_html(monkeypatch):
    """Each backend tries FETCH_ATTEMPTS_PER_LAYER times before failing."""
    pool = ScraperPool()
    attempts = {"count": 0}

    async def fake_once(backend_id: BackendId, url: str, **kwargs):
        attempts["count"] += 1
        if attempts["count"] < 2:
            return None, "fetch_failed"
        return "<html><body>ok</body></html>", None

    monkeypatch.setattr(pool, "_fetch_by_backend_once", fake_once)
    html, err = await pool._fetch_layer_with_retries(
        BackendId.DIRECT_HTTP,
        "https://example.com/p/1",
    )
    assert html is not None
    assert err is None
    assert attempts["count"] == 2


@pytest.mark.asyncio
async def test_paid_backend_gets_exactly_one_attempt(monkeypatch):
    """Every proxy-provider attempt is billed, failed ones included."""
    import app.modules.scraper.scraper_pool as sp

    pool = ScraperPool()
    attempts = {"count": 0}

    async def always_timeout(backend_id: BackendId, url: str, **kwargs):
        attempts["count"] += 1
        return None, "timeout"

    monkeypatch.setattr(pool, "_fetch_by_backend_once", always_timeout)
    monkeypatch.setattr(sp.asyncio, "sleep", AsyncMock())
    html, err = await pool._fetch_layer_with_retries(
        BackendId.PROXY_PROVIDER, "https://shop.example/p/1"
    )
    assert html is None and err == "timeout:proxy_provider"
    assert attempts["count"] == sp.PAID_BACKEND_ATTEMPTS == 1


@pytest.mark.asyncio
async def test_scrape_product_maps_fetch_failure_to_error(monkeypatch):
    """No HTML after all backends → success False with last backend error."""
    pool = ScraperPool()

    async def no_html(backend_id: BackendId, url: str, **kwargs):
        return None, "timeout"

    monkeypatch.setattr(pool, "_fetch_layer_with_retries", no_html)
    res = await pool.scrape_product("https://example.com/p/1")
    assert res.success is False
    assert "timeout" in (res.error or "").lower()


@pytest.mark.asyncio
async def test_timeout_is_not_retried_within_a_fetch(monkeypatch):
    """ldlc tarpit (2026-09-19): 3 x 25s direct + 3 x 35s render per listing."""
    pool = ScraperPool()
    attempts = {"count": 0}

    async def slow(backend_id: BackendId, url: str, **kwargs):
        attempts["count"] += 1
        return None, "timeout"

    monkeypatch.setattr(pool, "_fetch_by_backend_once", slow)
    html, err = await pool._fetch_layer_with_retries(BackendId.DIRECT_HTTP, "https://x/p")
    assert html is None and err == "timeout:direct_http"
    assert attempts["count"] == 1
