"""Legal clean-up WP2 — pool access: logged-in only, bounded, attributed.

Counsel §2.2/§3.8-3.9: no anonymous pool reads, no export, page size and
depth caps, a per-user hourly budget, per-source cap on unfiltered browsing,
source attribution on every item.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.common import rate_limit
from app.main import app
from app.modules.product_pool import api as pool_api
from app.modules.product_pool.service import (
    ProductPoolService,
    _row_to_pool_item,
    cap_per_source,
)
from tests.route_flatten import iter_app_routes


def _pool_routes():
    return [r for r in iter_app_routes(app) if r.path.startswith("/api/pool")]


def test_every_pool_route_requires_a_login_and_a_budget() -> None:
    from app.common.deps import get_current_user

    routes = _pool_routes()
    assert routes, "pool routes must be registered"
    for route in routes:
        deps = [d.call for d in route.dependant.dependencies] + [
            d.call for d in route.dependant.dependencies for d in d.dependencies
        ]
        names = {getattr(d, "__name__", "") for d in deps}
        assert get_current_user in deps or "get_current_user" in names, route.path
        assert "_dependency" in names, f"{route.path} lacks the pool rate-limit budget"


def test_export_route_is_gone() -> None:
    paths = {r.path for r in _pool_routes()}
    assert not any("export" in p for p in paths), paths
    assert not hasattr(ProductPoolService, "iter_export_rows")
    assert not hasattr(pool_api, "_EXPORT_COLUMNS")


def test_page_size_and_depth_caps_come_from_settings() -> None:
    assert pool_api.PAGE_SIZE_MAX == 50
    assert pool_api.OFFSET_MAX == 450  # 10 pages of 50
    route = next(r for r in _pool_routes() if r.path == "/api/pool/products")
    params = {p.name: p for p in route.dependant.query_params}
    limit_meta = [m for m in params["limit"].field_info.metadata if hasattr(m, "le")]
    offset_meta = [m for m in params["offset"].field_info.metadata if hasattr(m, "le")]
    assert limit_meta and limit_meta[0].le == 50
    assert offset_meta and offset_meta[0].le == 450


def test_items_carry_source_attribution() -> None:
    item = _row_to_pool_item(
        {
            "id": uuid4(),
            "product_id": uuid4(),
            "url": "https://shop.example/p/1",
            "marketplace_domain": "shop.example",
        }
    )
    assert item["external_url"] == "https://shop.example/p/1"
    assert item["source_domain"] == "shop.example"


class TestCapPerSource:
    def test_keeps_order_and_caps_each_marketplace(self) -> None:
        a, b, c = uuid4(), uuid4(), uuid4()
        rows = [(i, a) for i in range(5)] + [(10, b), (11, c), (12, b)] + [(20, a)]
        assert cap_per_source(rows, per_source=2, depth=100) == [0, 1, 10, 11, 12]

    def test_depth_stops_the_walk(self) -> None:
        a, b = uuid4(), uuid4()
        rows = [(0, a), (1, b), (2, a), (3, b), (4, a)]
        assert cap_per_source(rows, per_source=5, depth=3) == [0, 1, 2]

    def test_empty(self) -> None:
        assert cap_per_source([], 20, 500) == []


def test_unfiltered_list_goes_through_the_browse_set(monkeypatch) -> None:
    """No search / marketplace / category / country → the shared capped set,
    offset pagination only, total = size of the set."""
    svc = ProductPoolService(AsyncMock())
    browse = [uuid4() for _ in range(7)]
    monkeypatch.setattr(svc, "_browse_set", AsyncMock(return_value=browse))

    async def fake_execute(stmt):
        result = MagicMock()
        wanted = browse[2:5]
        result.mappings.return_value = [
            {"id": i, "product_id": uuid4(), "url": "u", "marketplace_domain": "d"} for i in wanted
        ]
        return result

    svc.db.execute = fake_execute
    monkeypatch.setattr(svc, "_get_recent_prices_map", AsyncMock(return_value={}))
    monkeypatch.setattr(svc, "_apply_display_currency", AsyncMock())
    items, total, meta = asyncio.run(svc.list_products(sort="recent", limit=3, offset=2))
    assert [i["id"] for i in items] == browse[2:5]
    assert total == 7
    assert meta == {"total_is_estimate": False, "next_cursor": None, "prev_cursor": None}


def test_filtered_list_does_not_use_the_browse_set(monkeypatch) -> None:
    svc = ProductPoolService(AsyncMock())
    browse_calls: list = []
    monkeypatch.setattr(svc, "_browse_set", AsyncMock(side_effect=lambda *a, **k: browse_calls.append(1)))
    result = MagicMock()
    result.mappings.return_value.all.return_value = []
    svc.db.execute = AsyncMock(return_value=result)
    monkeypatch.setattr(svc, "_count_pool", AsyncMock(return_value=(0, False)))
    items, _total, _meta = asyncio.run(
        svc.list_products(sort="recent", marketplace_id=uuid4(), limit=5, offset=0)
    )
    assert items == [] and browse_calls == []


class TestRateLimiter:
    def test_key_is_per_scope_user_and_hour(self) -> None:
        assert rate_limit.rate_limit_key("pool", "u1", now=7200.0) == "ratelimit:pool:u1:2"
        assert rate_limit.rate_limit_key("pool", "u1", now=7200.0 + 3599) == "ratelimit:pool:u1:2"
        assert rate_limit.rate_limit_key("pool", "u1", now=10800.0) == "ratelimit:pool:u1:3"

    def test_consume_counts_and_blocks_past_the_limit(self, monkeypatch) -> None:
        counter = {"n": 0}

        class _Pipe:
            def incr(self, _k):
                counter["n"] += 1
                return self

            def expire(self, _k, _ttl):
                return self

            async def execute(self):
                return [counter["n"], True]

        client = MagicMock()
        client.pipeline.return_value = _Pipe()
        monkeypatch.setattr(rate_limit, "_get_async_redis", lambda: client)
        results = [asyncio.run(rate_limit.consume("pool", "u1", 3)) for _ in range(4)]
        assert results == [(True, 2), (True, 1), (True, 0), (False, 0)]

    def test_redis_outage_fails_open(self, monkeypatch) -> None:
        def _boom():
            raise ConnectionError("down")

        monkeypatch.setattr(rate_limit, "_get_async_redis", _boom)
        monkeypatch.setattr(rate_limit, "_redis_down_logged", False)
        assert asyncio.run(rate_limit.consume("pool", "u1", 5)) == (True, 5)

    def test_dependency_raises_429_with_retry_after(self, monkeypatch) -> None:
        from fastapi import HTTPException

        monkeypatch.setattr(rate_limit, "consume", AsyncMock(return_value=(False, 0)))
        dep = rate_limit.user_rate_limit("pool", lambda: 10)
        request = MagicMock()
        user = MagicMock(id=uuid4())
        with pytest.raises(HTTPException) as info:
            asyncio.run(dep(request, user))
        assert info.value.status_code == 429
        assert info.value.headers["Retry-After"] == "3600"


def test_public_cache_layer_is_gone() -> None:
    import importlib

    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("app.common.public_cache")
    names = [type(m).__name__ for m in getattr(app, "user_middleware", [])] + [
        getattr(m, "cls", type(m)).__name__ for m in getattr(app, "user_middleware", [])
    ]
    assert "PublicETagMiddleware" not in names
