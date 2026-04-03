"""Unit tests for ScraperPool fetch retries (no real HTTP)."""

import pytest

from app.modules.scraper.scraper_pool import ScraperPool


@pytest.mark.asyncio
async def test_fetch_layer_retries_until_html(monkeypatch):
    """Each layer tries FETCH_ATTEMPTS_PER_LAYER times before failing."""
    pool = ScraperPool()
    attempts = {"count": 0}

    async def fake_once(layer: str, url: str):
        attempts["count"] += 1
        if attempts["count"] < 2:
            return None, "timeout"
        return "<html><body>ok</body></html>", None

    monkeypatch.setattr(pool, "_fetch_by_layer_once", fake_once)
    html, err = await pool._fetch_layer_with_retries("httpx", "https://example.com/p/1")
    assert html is not None
    assert err is None
    assert attempts["count"] == 2


@pytest.mark.asyncio
async def test_scrape_product_maps_fetch_failure_to_error(monkeypatch):
    """No HTML after all layers → success False with last layer error."""
    pool = ScraperPool()

    async def no_html(layer: str, url: str):
        return None, "timeout"

    monkeypatch.setattr(pool, "_fetch_layer_with_retries", no_html)
    res = await pool.scrape_product("https://example.com/p/1")
    assert res.success is False
    assert "timeout" in (res.error or "").lower()
