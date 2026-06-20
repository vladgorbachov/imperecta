"""Unit tests for tiered scrape strategy (_layer_order)."""

from __future__ import annotations

import pytest

from app.modules.scraper.fetch_backends import BackendId, ProxyProviderBackend
from app.modules.scraper.scraper_pool import ScraperPool


def test_layer_order_tier1_no_js():
    pool = ScraperPool()
    result = pool._layer_order(requires_js=False, scrape_tier=1)
    if ProxyProviderBackend.is_configured():
        assert result == [
            BackendId.DIRECT_HTTP,
            BackendId.PROXY_PROVIDER,
            BackendId.BROWSER_RENDER,
        ]
    else:
        assert result == [BackendId.DIRECT_HTTP, BackendId.BROWSER_RENDER]


def test_layer_order_tier1_requires_js_playwright_before_httpx(monkeypatch):
    monkeypatch.setattr(
        ProxyProviderBackend,
        "is_configured",
        staticmethod(lambda: True),
    )
    pool = ScraperPool()
    result = pool._layer_order(requires_js=True, scrape_tier=1)
    assert result == [
        BackendId.PROXY_PROVIDER,
        BackendId.BROWSER_RENDER,
        BackendId.DIRECT_HTTP,
    ]


def test_layer_order_tier2_raises_not_implemented():
    pool = ScraperPool()
    with pytest.raises(NotImplementedError, match="scrape_tier=2"):
        pool._layer_order(requires_js=False, scrape_tier=2)


def test_layer_order_unknown_tier_raises_value_error():
    pool = ScraperPool()
    with pytest.raises(ValueError, match="Unknown scrape_tier=99"):
        pool._layer_order(requires_js=False, scrape_tier=99)
