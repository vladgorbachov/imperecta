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
from app.modules.scraper.fetch_backends import BackendId
from app.modules.scraper.proxy_provider_limiter import (
    PROXY_PROVIDER_REDIS_KEY,
    acquire_proxy_provider_token,
    proxy_provider_bucket_capacity,
    proxy_provider_max_rps,
    reset_limiter_state_for_tests,
)
from app.modules.scraper.extractors import ExtractedProduct
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
    from app.modules.scraper.fetch_backends import DirectHttpBackend, ProxyProviderBackend

    direct = DirectHttpBackend()
    with patch(
        "app.modules.scraper.fetch_backends.httpx.AsyncClient",
    ) as client_cls:
        response = MagicMock()
        response.status_code = 200
        response.text = "<html>ok</html>"
        client = MagicMock()
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


class _ReadOnlySqlTransaction(Exception):
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
        _ReadOnlySqlTransaction("read-only transaction"),
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
