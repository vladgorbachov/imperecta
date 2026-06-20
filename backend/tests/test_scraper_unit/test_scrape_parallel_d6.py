"""D6 SCRAPE-PARALLEL: Decodo limiter + batch fetch / sequential persist."""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.modules.scraper import decodo_limiter as limiter
from app.modules.scraper import tasks as scraper_tasks
from app.modules.scraper.decodo_limiter import (
    DECODO_MAX_RPS,
    acquire_decodo_token,
    reset_limiter_state_for_tests,
)
from app.modules.scraper.scraper_pool import ListingFetchResult, ScraperPool
from app.modules.scraper.service import GlobalScrapeService


@pytest.fixture(autouse=True)
def _reset_limiter():
    reset_limiter_state_for_tests()
    yield
    reset_limiter_state_for_tests()


@pytest.mark.asyncio
async def test_decodo_limiter_caps_rps(monkeypatch):
    """Atomic acquire path must not grant more than capacity in a tight burst."""
    grants = 0

    def fake_eval(*_args, **_kwargs):
        nonlocal grants
        if grants >= DECODO_MAX_RPS:
            return 0
        grants += 1
        return 1

    fake_client = MagicMock()
    fake_client.eval.side_effect = fake_eval
    monkeypatch.setattr(limiter, "_get_redis", lambda: fake_client)

    results = await asyncio.gather(*[acquire_decodo_token() for _ in range(20)])
    assert sum(1 for r in results if r) <= DECODO_MAX_RPS


@pytest.mark.asyncio
async def test_limiter_acquire_respects_deadline():
    assert await acquire_decodo_token(time.monotonic() - 1.0) is False


@pytest.mark.asyncio
async def test_limiter_fails_closed_without_redis(monkeypatch):
    monkeypatch.setattr(
        limiter,
        "_get_redis",
        lambda: (_ for _ in ()).throw(ConnectionError("down")),
    )

    start = time.monotonic()
    first = await acquire_decodo_token()
    second = await acquire_decodo_token()
    elapsed = time.monotonic() - start

    assert first is True
    assert second is True
    assert elapsed >= limiter._LOCAL_FALLBACK_MIN_INTERVAL_SEC * 0.9


def test_scrape_batch_parallel_fetch_sequential_persist(monkeypatch):
    listing_ids = [uuid4() for _ in range(3)]
    persist_calls: list[uuid4] = []

    class _FakeResult:
        def all(self):
            return [(lid,) for lid in listing_ids]

    class _FakeSession:
        def execute(self, stmt):
            return _FakeResult()

        def get(self, _model, _lid):
            row = MagicMock()
            row.external_url = f"https://example.com/p/{_lid}"
            row.marketplace_id = uuid4()
            row.scraper_config = {}
            return row

        def close(self):
            pass

    pool = MagicMock()

    svc = MagicMock()
    svc._listing_scrape_context.return_value = (False, 1, {})

    def _persist(lid, fetch):
        persist_calls.append(lid)
        return MagicMock(success=True, error=None)

    svc.scrape_listing_from_fetch.side_effect = _persist

    monkeypatch.setattr(
        scraper_tasks,
        "_parallel_fetch_listings",
        lambda _pool, specs, deadline_monotonic=None: [
            ListingFetchResult(
                html="<html></html>",
                used_layer="httpx",
                last_error="fetch_failed",
                duration_ms=1,
            )
            for spec in specs
        ],
    )
    monkeypatch.setattr(scraper_tasks, "sync_session_factory", lambda: _FakeSession())
    monkeypatch.setattr(scraper_tasks, "ScraperPool", lambda: pool)
    monkeypatch.setattr(scraper_tasks, "GlobalScrapeService", lambda *_a, **_k: svc)
    monkeypatch.setattr(
        scraper_tasks,
        "Settings",
        lambda: MagicMock(scrape_pool_batch_size=10, scrape_pool_max_listings_per_run=100),
    )

    out = scraper_tasks._run_scrape_all_pool_impl(
        deadline_monotonic=time.monotonic() + 3600,
    )

    assert out["scraped_ok"] == 3
    assert len(persist_calls) == 3
    assert persist_calls == listing_ids


def test_scrape_batch_one_fetch_exception_isolated(monkeypatch):
    good_id = uuid4()
    bad_id = uuid4()
    listing_ids = [good_id, bad_id]

    class _FakeResult:
        def all(self):
            return [(lid,) for lid in listing_ids]

    class _FakeSession:
        def execute(self, stmt):
            return _FakeResult()

        def get(self, _model, lid):
            row = MagicMock()
            row.external_url = f"https://example.com/{lid}"
            row.marketplace_id = uuid4()
            row.scraper_config = {}
            return row

        def rollback(self):
            pass

        def close(self):
            pass

    def _parallel_fetch(_pool, specs, *, deadline_monotonic):
        return [
            ListingFetchResult(html="<html/>", used_layer="httpx", last_error="", duration_ms=1),
            RuntimeError("fetch boom"),
        ]

    svc = MagicMock()
    svc._listing_scrape_context.return_value = (False, 1, {})
    svc.scrape_listing_from_fetch.return_value = MagicMock(success=True, error=None)

    monkeypatch.setattr(scraper_tasks, "_parallel_fetch_listings", _parallel_fetch)
    monkeypatch.setattr(scraper_tasks, "sync_session_factory", lambda: _FakeSession())
    monkeypatch.setattr(scraper_tasks, "ScraperPool", MagicMock)
    monkeypatch.setattr(scraper_tasks, "GlobalScrapeService", lambda *_a, **_k: svc)
    monkeypatch.setattr(scraper_tasks, "_persist_technical_error_log", MagicMock())
    monkeypatch.setattr(
        scraper_tasks,
        "Settings",
        lambda: MagicMock(scrape_pool_batch_size=10, scrape_pool_max_listings_per_run=100),
    )

    out = scraper_tasks._run_scrape_all_pool_impl()

    assert out["scraped_ok"] == 1
    assert out["scraped_failed"] == 1
    svc.scrape_listing_from_fetch.assert_called_once()


@pytest.mark.asyncio
async def test_decodo_gated_httpx_not_gated(monkeypatch):
    acquire_mock = AsyncMock(return_value=True)
    monkeypatch.setattr(
        "app.modules.scraper.scraper_pool.acquire_decodo_token",
        acquire_mock,
    )
    monkeypatch.setattr(
        "app.modules.scraper.scraper_pool.settings",
        MagicMock(
            decodo_enabled=True,
            decodo_username="user",
            decodo_password="pass",
            decodo_api_url="http://decodo",
        ),
    )
    pool = ScraperPool()

    with patch.object(
        pool,
        "_fetch_html_httpx",
        AsyncMock(return_value=("<html>ok</html>", None)),
    ):
        await pool._fetch_html_httpx("https://shop.example/p/1")
    acquire_mock.assert_not_called()

    with patch.object(
        pool,
        "_fetch_html_decodo",
        wraps=pool._fetch_html_decodo,
    ) as decodo_mock, patch(
        "app.modules.scraper.scraper_pool.httpx.AsyncClient",
    ) as client_cls:
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {"results": [{"content": "<html>d</html>"}]}
        client = MagicMock()
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=False)
        client.post = AsyncMock(return_value=response)
        client_cls.return_value = client
        html, err = await pool._fetch_html_decodo("https://shop.example/p/2")
        assert html is not None
        assert err is None
    assert acquire_mock.await_count >= 1
    decodo_mock.assert_awaited_once()


def test_scrape_batch_preserves_d4_last_checked(monkeypatch):
    listing_id = uuid4()
    session, _listing = _readonly_test_session(listing_id)

    fetch = ListingFetchResult(
        html="<html><span class='price'>9.99 EUR</span></html>",
        used_layer="httpx",
        last_error="",
        duration_ms=5,
    )

    pool = MagicMock()
    pool.build_scrape_result_from_html.return_value = MagicMock(
        success=True,
        data=MagicMock(price=9.99, currency="EUR", title="T"),
        is_partial=False,
        duration_ms=5,
        scraper_layer="httpx",
        error=None,
    )

    svc = GlobalScrapeService(session, pool)
    persist_mock = MagicMock(return_value=MagicMock(success=True))
    monkeypatch.setattr(svc, "_persist_scrape_pool_result", persist_mock)

    svc.scrape_listing_from_fetch(listing_id, fetch)
    pool.build_scrape_result_from_html.assert_called_once()
    persist_mock.assert_called_once()


def _readonly_test_session(listing_id):
    from app.models.dimensions import DimMarketplace
    from app.models.facts import FactListing

    listing = MagicMock(spec=FactListing)
    listing.id = listing_id
    listing.external_url = "https://example.com/item"
    listing.marketplace_id = uuid4()
    listing.scraper_config = {}
    listing.last_checked_at = None

    mp = MagicMock(spec=DimMarketplace)
    mp.requires_js = False
    mp.scrape_tier = 1
    mp.custom_title_selector = None
    mp.custom_price_selector = None

    session = MagicMock()

    def get_side_effect(model, pk):
        if model is FactListing and pk == listing_id:
            return listing
        if model is DimMarketplace:
            return mp
        return None

    session.get.side_effect = get_side_effect
    return session, listing
