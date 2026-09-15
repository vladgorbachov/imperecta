"""Unit tests for access-mode fetch strategy (_layer_order + access_policy)."""

from __future__ import annotations

import pytest

from app.modules.scraper import access_policy
from app.modules.scraper.fetch_backends import BackendId, ProxyProviderBackend
from app.modules.scraper.scraper_pool import ScraperPool


@pytest.fixture(autouse=True)
def _clean_registry():
    saved = dict(access_policy._host_modes)
    access_policy._host_modes.clear()
    yield
    access_policy._host_modes.clear()
    access_policy._host_modes.update(saved)


def test_layer_order_direct_mode_never_spends_proxy(monkeypatch):
    """Quota protection: direct-mode shops get free backends only."""
    monkeypatch.setattr(
        ProxyProviderBackend, "is_configured", staticmethod(lambda: True)
    )
    pool = ScraperPool()
    result = pool._layer_order(requires_js=False, scrape_tier=1, url="https://shop.md/p")
    assert result == [BackendId.DIRECT_HTTP, BackendId.BROWSER_RENDER]
    assert BackendId.PROXY_PROVIDER not in result


def test_layer_order_requires_js_hint_renders_first():
    pool = ScraperPool()
    result = pool._layer_order(requires_js=True, scrape_tier=1, url="https://shop.md/p")
    assert result == [BackendId.BROWSER_RENDER, BackendId.DIRECT_HTTP]


def test_layer_order_render_mode_renders_first():
    access_policy.set_host_mode("https://spa-shop.example", "render")
    pool = ScraperPool()
    result = pool._layer_order(
        requires_js=False, scrape_tier=1, url="https://spa-shop.example/p/1"
    )
    assert result == [BackendId.BROWSER_RENDER, BackendId.DIRECT_HTTP]


def test_layer_order_proxy_mode_is_proxy_only(monkeypatch):
    monkeypatch.setattr(
        ProxyProviderBackend, "is_configured", staticmethod(lambda: True)
    )
    access_policy.set_host_mode("https://blocked-shop.example", "proxy")
    pool = ScraperPool()
    result = pool._layer_order(
        requires_js=False, scrape_tier=1, url="https://blocked-shop.example/p"
    )
    assert result == [BackendId.PROXY_PROVIDER]


def test_layer_order_proxy_mode_unconfigured_fails_honestly(monkeypatch):
    """No silent downgrade to a datacenter fetch that is known to be blocked."""
    monkeypatch.setattr(
        ProxyProviderBackend, "is_configured", staticmethod(lambda: False)
    )
    access_policy.set_host_mode("https://blocked-shop.example", "proxy")
    pool = ScraperPool()
    result = pool._layer_order(
        requires_js=False, scrape_tier=1, url="https://blocked-shop.example/p"
    )
    assert result == []


def test_proxy_render_flag_follows_access_mode():
    access_policy.set_host_mode("https://spa-blocked.example", "proxy_render")
    access_policy.set_host_mode("https://plain-blocked.example", "proxy")
    assert access_policy.wants_proxy_render("https://spa-blocked.example/p") is True
    assert access_policy.wants_proxy_render("https://plain-blocked.example/p") is False


def test_set_host_mode_ignores_garbage():
    access_policy.set_host_mode(None, "proxy")
    access_policy.set_host_mode("https://x.example", "teleport")
    assert access_policy.mode_for("https://x.example/p") == "direct"


def test_layer_order_tier2_raises_not_implemented():
    pool = ScraperPool()
    with pytest.raises(NotImplementedError, match="scrape_tier=2"):
        pool._layer_order(requires_js=False, scrape_tier=2)


def test_layer_order_unknown_tier_raises_value_error():
    pool = ScraperPool()
    with pytest.raises(ValueError, match="Unknown scrape_tier=99"):
        pool._layer_order(requires_js=False, scrape_tier=99)
