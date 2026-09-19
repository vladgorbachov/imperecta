"""Price-from-list ingestion (slice 2): matching, counters, sparse data shape."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.main import app
from app.models.facts import FactListing
from app.modules.ingestion import list_offers as lo


def _offer(url, price=99.5, currency="EUR", title="Widget"):
    return {
        "url": url,
        "price": price,
        "currency": currency,
        "title": title,
        "price_raw_text": f"{title} {price} {currency}",
    }


def _db_with_listings(urls, last_price=None):
    listings = {}
    for url in urls:
        h = FactListing.compute_url_hash(url)
        listings[h] = SimpleNamespace(url_hash=h, external_url=url, last_price=last_price)
    db = MagicMock()
    db.execute.return_value.scalars.return_value = list(listings.values())
    return db


def test_matches_known_urls_and_counts_unknown():
    known = "https://shop.example/p/known-1"
    db = _db_with_listings([known])
    persisted = SimpleNamespace(persisted=True, log_status="success")
    with patch.object(lo.IngestionService, "persist_extracted", return_value=persisted) as pe:
        counters = lo.ingest_list_offers(
            db,
            offers=[_offer(known), _offer("https://shop.example/p/stranger-2")],
        )
    assert counters == {
        "matched": 1,
        "saved": 1,
        "unknown": 1,
        "unpriced": 0,
        "suspicious": 0,
        "onboarded": 0,
    }
    data = pe.call_args.kwargs["data"]
    assert data.title == "Widget"
    assert data.price == 99.5
    assert data.currency == "EUR"
    assert data.page_role == "product"
    assert data.image_url is None and data.brand is None  # sparse by design


def test_no_change_counts_as_saved():
    known = "https://shop.example/p/known-1"
    db = _db_with_listings([known])
    unchanged = SimpleNamespace(persisted=False, log_status="no_change")
    with patch.object(lo.IngestionService, "persist_extracted", return_value=unchanged):
        counters = lo.ingest_list_offers(db, offers=[_offer(known)])
    assert counters["saved"] == 1


def test_priceless_offer_matched_but_not_ingested():
    known = "https://shop.example/p/known-1"
    db = _db_with_listings([known])
    with patch.object(lo.IngestionService, "persist_extracted") as pe:
        counters = lo.ingest_list_offers(db, offers=[_offer(known, price=None)])
    pe.assert_not_called()
    assert counters == {
        "matched": 1,
        "saved": 0,
        "unknown": 0,
        "unpriced": 1,
        "suspicious": 0,
        "onboarded": 0,
    }


def test_unknown_card_offer_onboards_when_marketplace_known():
    from uuid import uuid4 as _uuid4

    db = _db_with_listings([])
    mp_id = _uuid4()
    pool_result = SimpleNamespace(inserted=1, rejected=0)
    with patch.object(lo, "_normalize_name", wraps=lo._normalize_name), patch(
        "app.modules.discovery.gate_persist.write_pool_dtos_sync",
        return_value=pool_result,
    ) as wp:
        counters = lo.ingest_list_offers(
            db,
            offers=[_offer("https://shop.example/p/new-1")],
            marketplace_id=mp_id,
        )
    assert counters["unknown"] == 1
    assert counters["onboarded"] == 1
    dto = wp.call_args.args[0][0]
    assert dto.marketplace_id == mp_id
    assert dto.dim_product["name"] == "Widget"
    assert dto.fact_listing["external_url"] == "https://shop.example/p/new-1"


def test_unknown_offer_without_title_or_price_not_onboarded():
    from uuid import uuid4 as _uuid4

    db = _db_with_listings([])
    with patch(
        "app.modules.discovery.gate_persist.write_pool_dtos_sync"
    ) as wp:
        counters = lo.ingest_list_offers(
            db,
            offers=[
                _offer("https://shop.example/p/new-1", price=None),
                {"url": "https://shop.example/p/new-2", "price": 9.0, "title": "  "},
            ],
            marketplace_id=_uuid4(),
        )
    wp.assert_not_called()
    assert counters["unknown"] == 2
    assert counters["onboarded"] == 0


def test_price_far_from_last_price_is_held_back():
    known = "https://shop.example/p/known-1"
    db = _db_with_listings([known], last_price=355.00)
    with patch.object(lo.IngestionService, "persist_extracted") as pe:
        counters = lo.ingest_list_offers(db, offers=[_offer(known, price=2942.0)])
    pe.assert_not_called()
    assert counters["suspicious"] == 1
    assert counters["saved"] == 0


def test_plausible_change_with_last_price_still_saves():
    known = "https://shop.example/p/known-1"
    db = _db_with_listings([known], last_price=355.00)
    persisted = SimpleNamespace(persisted=True, log_status="success")
    with patch.object(lo.IngestionService, "persist_extracted", return_value=persisted):
        counters = lo.ingest_list_offers(db, offers=[_offer(known, price=299.0)])
    assert counters["saved"] == 1
    assert counters["suspicious"] == 0


def test_empty_offers_short_circuit():
    db = MagicMock()
    assert lo.ingest_list_offers(db, offers=[])["matched"] == 0
    db.execute.assert_not_called()


def test_harvest_endpoint_registered():
    schema = app.openapi()
    entry = schema["paths"].get("/api/admin/parsing/harvest-lists", {})
    assert "post" in entry


@pytest.mark.skipif(
    __import__("importlib").util.find_spec("imperecta_core") is None,
    reason="rust core not built in this environment",
)
def test_rust_list_offers_parity_shape():
    import imperecta_core as ic

    html = "<html><body>" + "".join(
        f'<div class="card"><a href="/p/w-{i}">Widget {i}</a>'
        f"<span>1 299,{i:02d} €</span></div>"
        for i in range(7)
    ) + "</body></html>"
    offers = ic.extract_list_offers(html, "https://shop.example/c/x")
    assert len(offers) == 7
    first = offers[0]
    assert first["url"] == "https://shop.example/p/w-0"
    assert first["price"] == 1299.0
    assert first["currency"] == "EUR"
    assert first["title"] == "Widget 0"


def test_harvest_rotation_picks_stalest_and_bumps():
    from unittest.mock import MagicMock
    from unittest.mock import patch as _patch

    from app.workers import harvest_tasks as ht

    client = MagicMock()
    client.zmscore.return_value = [100.0, None, 50.0]
    with _patch(
        "app.modules.scraper.pipeline.worker_log_relay._get_redis", return_value=client
    ):
        picked = ht._pick_rotation_shops(["a", "b", "c"], 2)
    # b never ran (None -> 0), c is older than a.
    assert picked == ["b", "c"]
    assert set(client.zadd.call_args.args[1].keys()) == {"b", "c"}


def test_harvest_tick_scheduled():
    from app.workers.celery_app import celery_app

    entry = celery_app.conf.beat_schedule.get("harvest-lists")
    assert entry and entry["task"] == "harvest_tick"


def test_shops_with_categories_guards_non_array_jsonb():
    """2026-09-19 incident: one legacy '{}' row made jsonb_array_length raise
    and took harvest down for EVERY shop. The query must gate the length
    call behind jsonb_typeof so non-array rows count as empty."""
    from unittest.mock import MagicMock
    from unittest.mock import patch as _patch

    from sqlalchemy.dialects import postgresql

    from app.workers import harvest_tasks as ht

    db = MagicMock()
    # first execute: marketplace rows; second: mv_marketplace_stats pools
    db.execute.return_value.all.side_effect = [[("shop_a", "mid-a")], [("mid-a", 4200)]]
    with _patch("app.database.sync_session_factory", return_value=db):
        assert ht._shops_with_categories_and_pool_sync() == [("shop_a", 4200)]
    stmt = db.execute.call_args_list[0].args[0]
    sql = str(stmt.compile(dialect=postgresql.dialect()))
    assert "jsonb_typeof(dim_marketplace.discovered_category_urls) = " in sql
    assert "CASE WHEN" in sql and "jsonb_array_length" in sql
    db.close.assert_called_once()


# --- paginated harvest cursor (2026-09-19) -------------------------------


class _FakeRedis:
    def __init__(self) -> None:
        self.h: dict[str, dict] = {}

    def hgetall(self, key):
        return dict(self.h.get(key, {}))

    def hset(self, key, mapping):
        self.h.setdefault(key, {}).update({k: str(v) for k, v in mapping.items()})


def test_pages_for_shop_walks_pool_once_per_pass():
    from app.workers import harvest_tasks as ht

    # pigu: 1,045,296 listings, 31 eligible shops, 30 offers/page ->
    # 1,161 pages/day needed; picked 48*6/31 = 9.3 times/day -> 125/run.
    assert ht.pages_for_shop(1_045_296, 31, 30.0) == 125
    # tiny shop clamps to the floor, unknown pool falls back to the default
    assert ht.pages_for_shop(48, 31, 30.0) == ht.HARVEST_PAGES_MIN
    assert ht.pages_for_shop(None, 31, 30.0) == ht.HARVEST_PAGES_PER_SHOP
    # a better measured yield needs fewer pages
    assert ht.pages_for_shop(1_045_296, 31, 60.0) < ht.pages_for_shop(1_045_296, 31, 30.0)


def test_harvest_walks_pagination_and_persists_cursor(monkeypatch):
    """Two categories; category A has 3 pages, B has 1. A run of limit=3
    fetches A1, A2, A3 and leaves the cursor on B; the next run resumes at B."""
    import types

    from app.workers import harvest_tasks as ht

    pages = {
        "https://s.example/a": ('<a rel="next" href="/a?page=2">n</a>', 3),
        "https://s.example/a?page=2": ('<a rel="next" href="/a?page=3">n</a>', 3),
        "https://s.example/a?page=3": ("<p>last</p>", 2),
        "https://s.example/b": ("<p>only</p>", 4),
    }
    fetched: list[str] = []

    class _Pool:
        async def fetch_listing_html(self, url, **_kw):
            fetched.append(url)
            html, _n = pages[url]
            return types.SimpleNamespace(html=html, deadline_skipped=False)

    fake_core = types.SimpleNamespace(
        extract_list_offers=lambda html, url: [{"url": f"{url}#{i}", "price": 1.0} for i in range(pages[url][1])]
    )
    monkeypatch.setitem(__import__("sys").modules, "imperecta_core", fake_core)
    monkeypatch.setattr("app.modules.scraper.scraper_pool.ScraperPool", _Pool)
    redis = _FakeRedis()
    monkeypatch.setattr("app.modules.scraper.pipeline.worker_log_relay._get_redis", lambda: redis)
    monkeypatch.setattr(
        ht, "_ingest_offers_sync", lambda offers, mid: {"matched": len(offers), "saved": len(offers)}
    )
    mp = SimpleNamespace(id="mid", base_url="https://s.example", domain="s.example",
                         requires_js=False, scrape_tier=1, rate_limit_delay=None,
                         access_mode="direct",
                         discovered_category_urls=["https://s.example/a", "https://s.example/b"])

    class _Res:
        def scalar_one_or_none(self):
            return mp

    class _Db:
        async def execute(self, _stmt):
            return _Res()

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return None

    class _Engine:
        async def dispose(self):
            return None

    monkeypatch.setattr(ht, "_make_session_factory", lambda: (_Engine(), lambda: _Db()))

    out = ht._run_async(ht._harvest("shop", 3))
    assert fetched == [
        "https://s.example/a",
        "https://s.example/a?page=2",
        "https://s.example/a?page=3",
    ]
    assert out["pages_fetched"] == 3 and out["matched"] == 8
    assert out["categories_done"] == 1 and out["cursor_category"] == 1
    assert 30 > out["yield_ema"] > 2  # EMA moved from the 30 prior toward ~3

    out2 = ht._run_async(ht._harvest("shop", 3))
    # resumed at B, then wrapped into pass 1 and re-fetched A1, A2
    assert fetched[3:] == [
        "https://s.example/b",
        "https://s.example/a",
        "https://s.example/a?page=2",
    ]
    assert out2["pass_no"] == 1


def test_harvest_budget_skip_keeps_cursor(monkeypatch):
    import types

    from app.workers import harvest_tasks as ht

    class _Pool:
        async def fetch_listing_html(self, url, **_kw):
            return types.SimpleNamespace(html=None, deadline_skipped=True)

    monkeypatch.setitem(__import__("sys").modules, "imperecta_core", types.SimpleNamespace(extract_list_offers=lambda h, u: []))
    monkeypatch.setattr("app.modules.scraper.scraper_pool.ScraperPool", _Pool)
    redis = _FakeRedis()
    redis.hset("harvest:cursor:shop", {"cat_idx": 1, "next_url": "https://s.example/b?page=4", "page": 3, "pass_no": 0, "yield_ema": 22.0})
    monkeypatch.setattr("app.modules.scraper.pipeline.worker_log_relay._get_redis", lambda: redis)
    mp = SimpleNamespace(id="mid", base_url="https://s.example", domain="s.example",
                         requires_js=False, scrape_tier=1, rate_limit_delay=None,
                         access_mode="proxy_render",
                         discovered_category_urls=["https://s.example/a", "https://s.example/b"])

    class _Res:
        def scalar_one_or_none(self):
            return mp

    class _Db:
        async def execute(self, _stmt):
            return _Res()

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return None

    class _Engine:
        async def dispose(self):
            return None

    monkeypatch.setattr(ht, "_make_session_factory", lambda: (_Engine(), lambda: _Db()))
    out = ht._run_async(ht._harvest("shop", 10))
    assert out["status"] == "budget_exhausted" and out["pages_fetched"] == 0
    saved = redis.hgetall("harvest:cursor:shop")
    assert (saved["cat_idx"], saved["next_url"], saved["page"]) == ("1", "https://s.example/b?page=4", "3")
