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


# --- sitemap lastmod (harvest optimisation #6) ---------------------------


def test_parse_sitemap_xml_keeps_lastmod():
    from app.modules.scraper.extractors import parse_sitemap_xml

    xml = (
        '<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        "<url><loc>https://s.example/p/1</loc><lastmod>2026-09-18</lastmod></url>"
        "<url><loc>https://s.example/p/2</loc></url></urlset>"
    )
    entries = parse_sitemap_xml(xml, "https://s.example")["url_entries"]
    assert [e["lastmod"] for e in entries] == ["2026-09-18", None]


def test_parse_lastmod_formats():
    from datetime import datetime, timezone

    from app.modules.discovery.sitemap_enumerator import parse_lastmod

    assert parse_lastmod("2026-09-18") == datetime(2026, 9, 18, tzinfo=timezone.utc)
    assert parse_lastmod("2026-09-18T10:20:30+02:00") == datetime(2026, 9, 18, 8, 20, 30, tzinfo=timezone.utc)
    assert parse_lastmod("2026-09-18T10:20:30Z") == datetime(2026, 9, 18, 10, 20, 30, tzinfo=timezone.utc)
    assert parse_lastmod("garbage") is None and parse_lastmod(None) is None


def test_lastmod_updates_are_gated_by_kind(monkeypatch):
    from datetime import datetime, timezone

    from app.modules.discovery import sitemap_enumerator as se

    signed: list = []

    def fake_authorize(*, table, kind, fields, reject_source):
        signed.append((table, kind, fields))
        return SimpleNamespace(passed=True, signed_record=("rec", fields))

    monkeypatch.setattr(
        "app.modules.data_firewall.update_validator.authorize_scrape_update", fake_authorize
    )
    written: list = []
    monkeypatch.setattr(
        "app.modules.persist.gate_rpc.exec_write_records",
        lambda db, chunk: written.extend(chunk) or len(chunk),
    )
    monkeypatch.setattr("app.database.sync_session_factory", lambda: MagicMock())
    when = datetime(2026, 9, 18, tzinfo=timezone.utc)
    assert se._write_lastmod_updates_sync([("h1", when), ("h2", when)]) == 2
    assert signed[0][:2] == ("fact_listing", "listing_sitemap_lastmod")
    assert signed[0][2] == {"url_hash": "h1", "sitemap_lastmod": when}


def test_sitemap_changed_signal_orders_frontier():
    from sqlalchemy.dialects import postgresql

    from app.modules.scraper import tasks as st

    sql = str(st._sitemap_changed().compile(dialect=postgresql.dialect()))
    assert "sitemap_lastmod > coalesce(fact_listing.last_checked_at" in sql


def test_sitemap_rescan_tick_dispatches_populated_shops(monkeypatch):
    from app.workers import onboarding_tasks as ob

    monkeypatch.setattr(ob, "_shops_for_rescan_sync", lambda: ["pigu_lt", "x-kom_pl"])
    calls: list = []
    monkeypatch.setattr(
        ob.sitemap_enumerate_marketplace,
        "apply_async",
        lambda args, kwargs=None, **opts: calls.append((args, kwargs, opts)),
    )
    assert ob.sitemap_rescan_tick.run() == {"status": "completed", "dispatched": 2}
    assert calls[0][0] == ["pigu_lt"] and calls[0][2]["priority"] == 8


def test_sitemap_rescan_scheduled_weekly():
    from app.workers.celery_app import celery_app

    entry = celery_app.conf.beat_schedule["sitemap-rescan"]
    assert entry["task"] == "sitemap_rescan_tick"
