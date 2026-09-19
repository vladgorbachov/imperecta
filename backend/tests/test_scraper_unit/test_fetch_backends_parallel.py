"""Parallel fetch backends: limiter + batch fetch / sequential persist."""

from __future__ import annotations

import asyncio
import threading
import time
import uuid
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.exc import OperationalError

from app.modules.ingestion.dto import IngestionResult
from app.modules.scraper import proxy_provider_limiter as limiter
from app.modules.scraper import service as scraper_service
from app.modules.scraper import tasks as scraper_tasks
from app.modules.scraper.extractors import ExtractedProduct
from app.modules.scraper.fetch_backends import BackendId
from app.modules.scraper.proxy_provider_limiter import (
    acquire_proxy_provider_token,
    proxy_provider_bucket_capacity,
    proxy_provider_max_rps,
    reset_limiter_state_for_tests,
)
from app.modules.scraper.scraper_pool import ListingFetchResult, PoolScrapeResult, ScraperPool
from app.modules.scraper.service import GlobalScrapeService


@pytest.fixture(autouse=True)
def _reset_limiter():
    reset_limiter_state_for_tests()
    yield
    reset_limiter_state_for_tests()


@pytest.mark.asyncio
async def test_proxy_provider_limiter_caps_rps(monkeypatch):
    """Atomic acquire path must not grant more than capacity in a tight burst."""
    grants = 0
    cap = proxy_provider_max_rps()
    lock = threading.Lock()

    def fake_eval(*_args, **_kwargs):
        nonlocal grants
        with lock:
            if grants >= cap:
                return 0
            grants += 1
            return 1

    fake_client = MagicMock()
    fake_client.eval.side_effect = fake_eval
    monkeypatch.setattr(limiter, "_get_redis", lambda: fake_client)

    results = await asyncio.gather(*[acquire_proxy_provider_token() for _ in range(20)])
    assert sum(1 for r in results if r) <= cap


@pytest.mark.asyncio
async def test_limiter_acquire_respects_deadline():
    assert await acquire_proxy_provider_token(time.monotonic() - 1.0) is False


@pytest.mark.asyncio
async def test_limiter_fails_closed_without_redis(monkeypatch):
    monkeypatch.setattr(
        limiter,
        "_get_redis",
        lambda: (_ for _ in ()).throw(ConnectionError("down")),
    )

    start = time.monotonic()
    first = await acquire_proxy_provider_token()
    second = await acquire_proxy_provider_token()
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
                used_backend=BackendId.DIRECT_HTTP,
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
            ListingFetchResult(html="<html/>", used_backend=BackendId.DIRECT_HTTP, last_error="", duration_ms=1),
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
async def test_proxy_provider_gated_direct_http_not_gated(monkeypatch):
    acquire_mock = AsyncMock(return_value=True)
    monkeypatch.setattr(
        "app.modules.scraper.fetch_backends.acquire_proxy_provider_token",
        acquire_mock,
    )
    monkeypatch.setattr(
        "app.modules.scraper.fetch_backends.settings",
        MagicMock(
            proxy_provider_enabled=True,
            proxy_provider_username="user",
            proxy_provider_password="pass",
            proxy_provider_api_url="http://proxy-provider",
        ),
    )
    from app.modules.scraper import fetch_backends as fb
    from app.modules.scraper.fetch_backends import DirectHttpBackend, ProxyProviderBackend

    # The per-loop pooled client survives across tests under the session
    # event loop — drop it so the patched AsyncClient class is used.
    fb._loop_http_clients.clear()
    direct = DirectHttpBackend()
    with patch(
        "app.modules.scraper.fetch_backends.httpx.AsyncClient",
    ) as client_cls:
        response = MagicMock()
        response.status_code = 200
        response.text = "<html>ok</html>"
        client = MagicMock()
        client.is_closed = False  # pooled-client liveness check
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=False)
        client.get = AsyncMock(return_value=response)
        client_cls.return_value = client
        html, err = await direct.fetch("https://shop.example/p/1")
        assert html is not None
        assert err is None
    acquire_mock.assert_not_called()

    proxy = ProxyProviderBackend()
    with patch(
        "app.modules.scraper.fetch_backends.httpx.AsyncClient",
    ) as client_cls:
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {"results": [{"content": "<html>d</html>"}]}
        client = MagicMock()
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=False)
        client.post = AsyncMock(return_value=response)
        client_cls.return_value = client
        html, err = await proxy.fetch("https://shop.example/p/2")
        assert html is not None
        assert err is None
    assert acquire_mock.await_count >= 1


def test_scrape_batch_preserves_d4_last_checked(monkeypatch):
    listing_id = uuid4()
    session, _listing = _readonly_test_session(listing_id)

    fetch = ListingFetchResult(
        html="<html><span class='price'>9.99 EUR</span></html>",
        used_backend=BackendId.DIRECT_HTTP,
        last_error="",
        duration_ms=5,
    )

    pool = MagicMock()
    pool.build_scrape_result_from_html.return_value = MagicMock(
        success=True,
        data=MagicMock(price=9.99, currency="EUR", title="T"),
        is_partial=False,
        duration_ms=5,
        fetch_backend="direct_http",
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


class _FaithfulTokenBucketRedis:
    """In-memory Redis eval that mirrors proxy_provider_limiter._ACQUIRE_LUA arithmetic.

    A threading lock serializes eval calls the same way Redis Lua does atomically.
    """

    def __init__(self) -> None:
        self._buckets: dict[str, dict[str, float]] = {}
        self._lock = threading.Lock()

    def eval(
        self,
        _script: str,
        _numkeys: int,
        key: str,
        now_ms: int,
        rate: int,
        capacity: int,
        requested: int,
    ) -> int:
        with self._lock:
            bucket = self._buckets.setdefault(key, {})
            tokens = bucket.get("tokens")
            last_refill = bucket.get("last_refill")
            now = float(now_ms)

            if tokens is None:
                tokens = float(capacity)
                last_refill = now

            elapsed = max(0.0, now - last_refill) / 1000.0
            tokens = min(float(capacity), tokens + elapsed * float(rate))

            if tokens < float(requested):
                bucket["tokens"] = tokens
                bucket["last_refill"] = now
                return 0

            tokens -= float(requested)
            bucket["tokens"] = tokens
            bucket["last_refill"] = now
            return 1


@pytest.mark.asyncio
async def test_limiter_lua_bucket_no_overshoot_burst(monkeypatch):
    """GAP (a): real token-bucket math cannot grant more than capacity in one instant."""
    store = _FaithfulTokenBucketRedis()
    monkeypatch.setattr(limiter, "_get_redis", lambda: store)
    fixed_now = 1_700_000_000_000
    monkeypatch.setattr(time, "time", lambda: fixed_now / 1000.0)

    async def _instant_sleep(_sec: float) -> None:
        return None

    monkeypatch.setattr(asyncio, "sleep", _instant_sleep)

    results = await asyncio.gather(*[acquire_proxy_provider_token() for _ in range(20)])
    granted = sum(1 for ok in results if ok)
    assert granted <= proxy_provider_bucket_capacity()


@pytest.mark.asyncio
async def test_limiter_lua_bucket_no_overshoot_refill_window(monkeypatch):
    """GAP (a): grants over a window stay within capacity + rate * window."""
    store = _FaithfulTokenBucketRedis()
    monkeypatch.setattr(limiter, "_get_redis", lambda: store)
    window_sec = 0.5
    start_ms = 1_700_000_000_000
    clock = {"ms": start_ms}

    def _time() -> float:
        return clock["ms"] / 1000.0

    monkeypatch.setattr(time, "time", _time)

    async def _sleep(sec: float) -> None:
        clock["ms"] += int(sec * 1000)

    monkeypatch.setattr(asyncio, "sleep", _sleep)

    granted = 0
    end_ms = start_ms + int(window_sec * 1000)
    while clock["ms"] <= end_ms:
        if await acquire_proxy_provider_token():
            granted += 1

    max_allowed = proxy_provider_bucket_capacity() + int(
        window_sec * proxy_provider_max_rps()
    ) + 1
    assert granted <= max_allowed


class _ReadOnlySqlTransactionError(Exception):
    pgcode = "25006"


def _parallel_path_session(*, listing_id: uuid.UUID):
    from app.models.dimensions import DimMarketplace, DimProduct
    from app.models.facts import FactListing

    product_id = uuid.uuid4()
    marketplace_id = uuid.uuid4()
    listing = FactListing(
        id=listing_id,
        product_id=product_id,
        marketplace_id=marketplace_id,
        external_url="https://example.com/item",
        url_hash=FactListing.compute_url_hash("https://example.com/item"),
    )
    listing.last_checked_at = None
    product = DimProduct(
        id=product_id,
        name="product",
        name_normalized="product",
    )
    mp = DimMarketplace(
        id=marketplace_id,
        marketplace_code=f"mp_{uuid.uuid4().hex[:8]}",
        name="MP",
        source_type="direct_retail",
        country_code="US",
        operates_in=["US"],
        domain="example.com",
        base_url="https://example.com",
        currency_code="USD",
        scraper_type="httpx",
    )
    session = MagicMock()

    def get_side_effect(model, pk):
        if model is FactListing and pk == listing_id:
            return listing
        if model is DimProduct and pk == product_id:
            return product
        if model is DimMarketplace and pk == marketplace_id:
            return mp
        return None

    session.get.side_effect = get_side_effect
    session.add = MagicMock()
    session.execute = MagicMock()
    session.flush = MagicMock()
    session.commit = MagicMock()
    session.rollback = MagicMock()
    session.connection = MagicMock()
    return session, listing


@pytest.mark.integration
def test_parallel_persist_success_advances_last_checked(monkeypatch):
    """GAP (b): success on scrape_listing_from_fetch advances last_checked_at."""
    listing_id = uuid.uuid4()
    session, listing = _parallel_path_session(listing_id=listing_id)
    pool = MagicMock(spec=ScraperPool)
    pool.build_scrape_result_from_html.return_value = PoolScrapeResult(
        success=True,
        url=listing.external_url,
        data=ExtractedProduct(title="T", price=10.0, currency="USD"),
        fetch_backend="direct_http",
    )
    monkeypatch.setattr(
        scraper_service.IngestionService,
        "persist_extracted",
        lambda self, **kwargs: IngestionResult(
            persisted=True,
            log_status="success",
        ),
    )
    monkeypatch.setattr(scraper_service, "_today_date_id", lambda _db: 20990101)

    svc = GlobalScrapeService(session, pool)
    fetch = ListingFetchResult(
        html="<html><span class='price'>10 USD</span></html>",
        used_backend=BackendId.DIRECT_HTTP,
        last_error="",
        duration_ms=3,
    )
    out = svc.scrape_listing_from_fetch(listing_id, fetch)

    assert out is not None and out.success is True
    assert listing.last_checked_at is not None


def test_parallel_persist_read_only_does_not_advance_last_checked(monkeypatch):
    """GAP (b): read-only housekeeping failure stays retriable, cohort retained."""
    listing_id = uuid.uuid4()
    session, listing = _parallel_path_session(listing_id=listing_id)
    session.commit.side_effect = OperationalError(
        "stmt",
        {},
        _ReadOnlySqlTransactionError("read-only transaction"),
    )
    invalidate = MagicMock()
    monkeypatch.setattr(scraper_service, "invalidate_sync_session", invalidate)
    pool = MagicMock(spec=ScraperPool)
    pool.build_scrape_result_from_html.return_value = PoolScrapeResult(
        success=False,
        url=listing.external_url,
        error="fetch_failed:direct_http",
        data=None,
        fetch_backend="direct_http",
    )

    svc = GlobalScrapeService(session, pool)
    fetch = ListingFetchResult(
        html=None,
        used_backend=BackendId.DIRECT_HTTP,
        last_error="fetch_failed:direct_http",
        duration_ms=2,
    )
    out = svc.scrape_listing_from_fetch(listing_id, fetch)

    assert out is not None
    assert out.error == "read_only_retriable"
    assert listing.last_checked_at is None
    invalidate.assert_called_once()


@pytest.mark.integration
def test_parallel_persist_honest_absent_advances_last_checked(monkeypatch):
    """GAP (b): honest-absent verdict advances last_checked_at on parallel path."""
    listing_id = uuid.uuid4()
    session, listing = _parallel_path_session(listing_id=listing_id)
    pool = MagicMock(spec=ScraperPool)
    pool.build_scrape_result_from_html.return_value = PoolScrapeResult(
        success=False,
        url=listing.external_url,
        error="price_not_found",
        data=None,
        fetch_backend="direct_http",
    )

    svc = GlobalScrapeService(session, pool)
    fetch = ListingFetchResult(
        html="<html>no price</html>",
        used_backend=BackendId.DIRECT_HTTP,
        last_error="price_not_found",
        duration_ms=4,
    )
    out = svc.scrape_listing_from_fetch(listing_id, fetch)

    assert out is not None
    assert out.log_status == "price_not_found"
    assert listing.last_checked_at is not None


def test_parallel_persist_technical_failure_does_not_advance(monkeypatch):
    """GAP (b): non-read-only persist failure leaves last_checked_at unchanged."""
    listing_id = uuid.uuid4()
    session, listing = _parallel_path_session(listing_id=listing_id)
    session.commit.side_effect = RuntimeError("disk full")
    pool = MagicMock(spec=ScraperPool)
    pool.build_scrape_result_from_html.return_value = PoolScrapeResult(
        success=False,
        url=listing.external_url,
        error="fetch_failed:direct_http",
        data=None,
        fetch_backend="direct_http",
    )

    svc = GlobalScrapeService(session, pool)
    fetch = ListingFetchResult(
        html=None,
        used_backend=BackendId.DIRECT_HTTP,
        last_error="fetch_failed:direct_http",
        duration_ms=2,
    )
    out = svc.scrape_listing_from_fetch(listing_id, fetch)

    assert out is not None
    assert out.error == "persist_failed"
    assert listing.last_checked_at is None


def test_batch_loop_deadline_retains_cohort(monkeypatch):
    """GAP (c): deadline between fetch and persist skips remaining listings."""
    lid_done = uuid4()
    lid_skipped = uuid4()
    listing_ids = [lid_done, lid_skipped]
    deadline = 1000.0
    monotonic_values = iter([900.0, 900.0, 900.0, 1100.0])
    monkeypatch.setattr(time, "monotonic", lambda: next(monotonic_values, 1100.0))

    listings: dict = {}

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
            row.last_checked_at = None
            listings[lid] = row
            return row

        def close(self):
            pass

    persist_calls: list[uuid.UUID] = []

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
                html="<html/>",
                used_backend=BackendId.DIRECT_HTTP,
                last_error="",
                duration_ms=1,
            )
            for _spec in specs
        ],
    )
    monkeypatch.setattr(scraper_tasks, "sync_session_factory", lambda: _FakeSession())
    monkeypatch.setattr(scraper_tasks, "ScraperPool", MagicMock)
    monkeypatch.setattr(scraper_tasks, "GlobalScrapeService", lambda *_a, **_k: svc)
    monkeypatch.setattr(
        scraper_tasks,
        "Settings",
        lambda: MagicMock(scrape_pool_batch_size=10, scrape_pool_max_listings_per_run=100),
    )

    out = scraper_tasks._run_scrape_all_pool_impl(deadline_monotonic=deadline)

    assert out["scraped_ok"] == 1
    assert out["scraped_failed"] == 0
    assert out["deadline_exhausted"] is True
    assert persist_calls == [lid_done]
    assert listings[lid_skipped].last_checked_at is None


def test_batch_loop_deadline_skipped_fetch_not_counted_failed(monkeypatch):
    """GAP (c): deadline_skipped fetch leaves listing unscored (cohort retained)."""
    good_id = uuid4()
    skipped_id = uuid4()
    listing_ids = [good_id, skipped_id]

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
            row.last_checked_at = None
            return row

        def close(self):
            pass

    svc = MagicMock()
    svc._listing_scrape_context.return_value = (False, 1, {})
    svc.scrape_listing_from_fetch.return_value = MagicMock(success=True, error=None)

    monkeypatch.setattr(
        scraper_tasks,
        "_parallel_fetch_listings",
        lambda _pool, specs, deadline_monotonic=None: [
            ListingFetchResult(
                html="<html/>",
                used_backend=BackendId.DIRECT_HTTP,
                last_error="",
                duration_ms=1,
            ),
            ListingFetchResult(
                html=None,
                used_backend=None,
                last_error="proxy_provider_deadline",
                duration_ms=1,
                deadline_skipped=True,
            ),
        ],
    )
    monkeypatch.setattr(scraper_tasks, "sync_session_factory", lambda: _FakeSession())
    monkeypatch.setattr(scraper_tasks, "ScraperPool", MagicMock)
    monkeypatch.setattr(scraper_tasks, "GlobalScrapeService", lambda *_a, **_k: svc)
    monkeypatch.setattr(
        scraper_tasks,
        "Settings",
        lambda: MagicMock(scrape_pool_batch_size=10, scrape_pool_max_listings_per_run=100),
    )

    out = scraper_tasks._run_scrape_all_pool_impl(
        deadline_monotonic=time.monotonic() + 3600,
    )

    assert out["scraped_ok"] == 1
    assert out["scraped_failed"] == 0
    svc.scrape_listing_from_fetch.assert_called_once()


@pytest.mark.asyncio
async def test_proxy_daily_budget_cap_blocks_before_spending(monkeypatch):
    """Cap reached -> honest budget skip, no RPS token, no provider POST."""
    from app.modules.scraper import fetch_backends as fb

    acquire_mock = AsyncMock(return_value=True)
    monkeypatch.setattr(fb, "acquire_proxy_provider_token", acquire_mock)
    monkeypatch.setattr(fb, "daily_budget_exhausted_sync", lambda: True)
    monkeypatch.setattr(
        fb,
        "settings",
        MagicMock(
            proxy_provider_enabled=True,
            proxy_provider_username="user",
            proxy_provider_password="pass",
            proxy_provider_api_url="http://proxy-provider",
        ),
    )
    with patch("app.modules.scraper.fetch_backends.httpx.AsyncClient") as client_cls:
        html, err = await fb.ProxyProviderBackend().fetch("https://shop.example/p/3")
    assert (html, err) == (None, limiter.PROXY_PROVIDER_BUDGET_ERROR)
    acquire_mock.assert_not_called()
    client_cls.assert_not_called()


def test_billing_cycle_renews_on_the_16th(monkeypatch):
    import calendar
    import time as _time

    monkeypatch.setattr(limiter, "Settings", lambda: MagicMock(proxy_provider_billing_day=16))
    sept19 = calendar.timegm(_time.strptime("2026-09-19", "%Y-%m-%d"))
    start, end = limiter.billing_cycle(sept19)
    assert (start.isoformat(), end.isoformat()) == ("2026-09-16", "2026-10-16")
    sept3 = calendar.timegm(_time.strptime("2026-09-03", "%Y-%m-%d"))
    start, end = limiter.billing_cycle(sept3)
    assert (start.isoformat(), end.isoformat()) == ("2026-08-16", "2026-09-16")
    # renewal day past a short month clamps to its last day
    monkeypatch.setattr(limiter, "Settings", lambda: MagicMock(proxy_provider_billing_day=31))
    feb10 = calendar.timegm(_time.strptime("2026-02-10", "%Y-%m-%d"))
    start, end = limiter.billing_cycle(feb10)
    assert (start.isoformat(), end.isoformat()) == ("2026-01-31", "2026-02-28")


def test_cycle_budget_spreads_remaining_over_days_left(monkeypatch):
    """Decodo $19 plan at the measured $0.95/1k = 20,000 requests per cycle;
    cycle 2026-09-16..10-16. On the 19th (27 days left) after 4,891 spent on
    the 18th and 0 today -> allowance (20000 - 4891) // 27 = 559."""
    import calendar
    import time as _time

    store = MagicMock()
    monkeypatch.setattr(limiter, "_get_redis", lambda: store)
    monkeypatch.setattr(limiter, "proxy_provider_monthly_cap", lambda: 20_000)
    monkeypatch.setattr(limiter, "proxy_provider_daily_cap", lambda: 0)
    monkeypatch.setattr(limiter, "Settings", lambda: MagicMock(proxy_provider_billing_day=16))
    sept19 = calendar.timegm(_time.strptime("2026-09-19", "%Y-%m-%d"))
    usage = {"20260918": "4891", "20260915": "99999"}  # the 15th is the previous cycle

    def mget(keys):
        if keys and keys[0].startswith(limiter.PROXY_COST_KEY_PREFIX):
            return [None for _ in keys]  # no cost counters yet -> plain counts
        return [usage.get(k.removeprefix(limiter.PROXY_USAGE_KEY_PREFIX)) for k in keys]

    store.mget.side_effect = mget
    status = limiter.budget_status_sync(sept19)
    assert (status["cycle_start"], status["cycle_end"]) == ("2026-09-16", "2026-10-16")
    assert status["days_left"] == 27
    assert status["month_used"] == 4891
    assert status["daily_allowance"] == (20_000 - 4_891) // 27 == 559
    assert status["exhausted"] is False

    usage["20260919"] = "559"
    assert limiter.budget_status_sync(sept19)["exhausted"] is True
    # cycle cap alone is decisive even mid-day
    usage["20260919"] = "0"
    usage["20260916"] = "30000"
    assert limiter.budget_status_sync(sept19)["exhausted"] is True


def test_daily_budget_guard_disabled_and_fail_open(monkeypatch):
    store = MagicMock()
    monkeypatch.setattr(limiter, "_get_redis", lambda: store)
    monkeypatch.setattr(limiter, "Settings", lambda: MagicMock(proxy_provider_billing_day=16))
    # No budget and no hard cap -> guard off, Redis never consulted.
    monkeypatch.setattr(limiter, "proxy_provider_monthly_cap", lambda: 0)
    monkeypatch.setattr(limiter, "proxy_provider_daily_cap", lambda: 0)
    assert limiter.daily_budget_exhausted_sync() is False
    store.mget.assert_not_called()
    # Hard daily cap works without a monthly budget (count 10, cost 10.00).
    monkeypatch.setattr(limiter, "proxy_provider_daily_cap", lambda: 10)
    store.mget.side_effect = [["10"], ["1000"]]
    assert limiter.daily_budget_exhausted_sync() is True
    # Redis trouble fails open.
    store.mget.side_effect = ConnectionError("redis down")
    assert limiter.daily_budget_exhausted_sync() is False


def test_monthly_cap_derives_from_budget_and_price(monkeypatch):
    monkeypatch.setattr(
        limiter,
        "Settings",
        lambda: MagicMock(proxy_provider_monthly_budget_usd=49.0, proxy_cost_per_1k_usd=0.82),
    )
    assert limiter.proxy_provider_monthly_cap() == 59_756
    monkeypatch.setattr(
        limiter,
        "Settings",
        lambda: MagicMock(proxy_provider_monthly_budget_usd=0, proxy_cost_per_1k_usd=0.95),
    )
    assert limiter.proxy_provider_monthly_cap() == 0


@pytest.mark.asyncio
async def test_budget_skip_surfaces_as_empty_result(monkeypatch):
    from app.modules.scraper import scraper_pool as sp

    pool = sp.ScraperPool()
    monkeypatch.setattr(
        pool, "_layer_order", lambda *a, **k: [sp.BackendId.PROXY_PROVIDER]
    )

    async def budget_once(_backend_id, _url, **_kw):
        return None, limiter.PROXY_PROVIDER_BUDGET_ERROR

    monkeypatch.setattr(pool, "_fetch_by_backend_once", budget_once)
    result = await pool.scrape_product("https://shop.example/p/4", requires_js=False)
    assert result.success is False
    assert result.is_empty is True
    assert result.error == limiter.PROXY_PROVIDER_BUDGET_ERROR


def test_cost_weighted_usage_lets_nojs_buy_more(monkeypatch):
    """A no-JS fetch is charged nojs/js of a JS fetch (0.38/0.82 = 46%)."""
    monkeypatch.setattr(
        limiter,
        "Settings",
        lambda: MagicMock(
            proxy_cost_per_1k_usd=0.82, proxy_cost_nojs_per_1k_usd=0.38, proxy_provider_billing_day=19
        ),
    )
    assert limiter.cost_weight_hundredths(True) == 100
    assert limiter.cost_weight_hundredths(False) == 46
    store = MagicMock()
    monkeypatch.setattr(limiter, "_get_redis", lambda: store)
    limiter._record_usage_sync(render_js=False)
    incrby_key, weight = store.incrby.call_args.args
    assert incrby_key.startswith(limiter.PROXY_COST_KEY_PREFIX) and weight == 46
    # status pacing reads the cost counter: 100 no-JS fetches = 46 JS-equivalents
    monkeypatch.setattr(limiter, "proxy_provider_monthly_cap", lambda: 1000)
    monkeypatch.setattr(limiter, "proxy_provider_daily_cap", lambda: 0)
    store.mget.side_effect = [["100"], ["4600"]]
    status = limiter.budget_status_sync()
    assert status["today_used"] == 46
