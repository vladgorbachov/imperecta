"""Unit tests for tiered scrape strategy (_layer_order)."""

from __future__ import annotations

import pytest

import app.modules.scraper.scraper_pool as sp
from app.modules.scraper.scraper_pool import ScraperPool


def test_layer_order_tier1_no_js():
    pool = ScraperPool()
    result = pool._layer_order(requires_js=False, scrape_tier=1)
    if sp.settings.decodo_enabled and sp.settings.decodo_username and sp.settings.decodo_password:
        assert result == ["decodo", "httpx", "playwright"]
    else:
        assert result == ["httpx", "playwright"]


def test_layer_order_tier1_requires_js_playwright_before_httpx(monkeypatch):
    monkeypatch.setattr(sp.settings, "decodo_enabled", True)
    monkeypatch.setattr(sp.settings, "decodo_username", "u")
    monkeypatch.setattr(sp.settings, "decodo_password", "p")
    pool = ScraperPool()
    result = pool._layer_order(requires_js=True, scrape_tier=1)
    assert result == ["decodo", "playwright", "httpx"]


def test_layer_order_tier2_raises_not_implemented():
    pool = ScraperPool()
    with pytest.raises(NotImplementedError, match="scrape_tier=2"):
        pool._layer_order(requires_js=False, scrape_tier=2)


def test_layer_order_unknown_tier_raises_value_error():
    pool = ScraperPool()
    with pytest.raises(ValueError, match="Unknown scrape_tier=99"):
        pool._layer_order(requires_js=False, scrape_tier=99)
