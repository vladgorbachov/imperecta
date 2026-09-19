"""Category pages harvested from sitemaps (harvest optimisation #3)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.modules.discovery import sitemap_categories as sc


def test_category_like_keeps_listings_and_drops_products_chrome_facets():
    assert sc.category_like("https://shop.example/catalog/laptops") is True
    assert sc.category_like("https://shop.example/c/tv-audio/televizory") is True
    # product: slug with a 6+ digit id / numeric product path
    assert sc.category_like("https://shop.example/catalog/laptops/lenovo-ideapad-3-1234567") is False
    assert sc.category_like("https://shop.example/product/12345") is False
    # chrome / facets / homepage / query strings
    assert sc.category_like("https://shop.example/login") is False
    assert sc.category_like("https://shop.example/c80196/strana-90098=675621/") is False
    assert sc.category_like("https://shop.example/") is False
    assert sc.category_like("https://shop.example/catalog/laptops?page=2") is False


def test_collect_prefers_category_shards_and_caps(monkeypatch):
    monkeypatch.setattr(sc, "SITEMAP_CATEGORY_URLS_MAX", 3)
    entries = [
        ("https://www.shop.example/catalog/phones", "https://shop.example/sitemap-1.xml"),
        ("https://shop.example/catalog/dropped", "https://shop.example/sitemap-products.xml"),
        ("https://shop.example/catalog/tv", "https://shop.example/sitemap-categories.xml"),
        ("https://shop.example/catalog/tv", "https://shop.example/sitemap-categories.xml"),  # dup
        ("https://other.example/catalog/x", "https://shop.example/sitemap-categories.xml"),  # foreign host
        ("https://shop.example/catalog/audio", "https://shop.example/sitemap-kategorie.xml"),
        ("https://shop.example/catalog/pc", "https://shop.example/sitemap-1.xml"),
    ]
    out = sc.collect_category_urls(entries, "shop.example")
    assert out == [
        "https://shop.example/catalog/tv",
        "https://shop.example/catalog/audio",
        "https://www.shop.example/catalog/phones",
    ]


def test_merge_keeps_discovery_order_first():
    merged = sc.merge_category_urls(["https://s/a", "https://s/b"], ["https://s/b", "https://s/c"])
    assert merged == ["https://s/a", "https://s/b", "https://s/c"]
    assert sc.merge_category_urls("{}", ["https://s/c"]) == ["https://s/c"]


@pytest.mark.asyncio
async def test_publish_writes_only_when_new(monkeypatch):
    calls: list = []

    async def fake_write(**kw):
        calls.append(kw)

    monkeypatch.setattr("app.modules.persist.meta_write.write_meta_async", fake_write)
    mp = SimpleNamespace(id="mid", discovered_category_urls=["https://s/a"])
    assert await sc.publish_category_urls(mp, ["https://s/a"]) == 0
    assert calls == []
    assert await sc.publish_category_urls(mp, ["https://s/b"]) == 1
    assert calls[0]["table"] == "dim_marketplace" and calls[0]["operation"] == "update"
    assert calls[0]["fields"]["id"] == "mid"


def test_shard_categories_stash_and_finisher_merge(monkeypatch):
    from app.workers import onboarding_tasks as ob

    redis = MagicMock()
    redis.smembers.return_value = {b"https://s/b", b"https://s/a"}
    monkeypatch.setattr("app.modules.scraper.pipeline.worker_log_relay._get_redis", lambda: redis)
    ob._stash_shard_categories("shop", "run", ["https://s/a", "https://s/b"])
    redis.sadd.assert_called_once_with("enumrun:shop:run:cats", "https://s/a", "https://s/b")
    assert ob._pop_run_categories("shop", "run") == ["https://s/a", "https://s/b"]
    redis.delete.assert_called_once_with("enumrun:shop:run:cats")
