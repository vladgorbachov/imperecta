"""Fan-out coordinators: enumeration sharding + PDP scrape dispatcher."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

from app.modules.scraper import tasks as scraper_tasks
from app.workers import onboarding_tasks as ob


def test_enumerate_coordinator_shards_and_sets_pending(monkeypatch) -> None:
    mp = SimpleNamespace(id=uuid4(), catalog_size_estimate=None)
    shard_urls = [f"https://shop.example/sitemap-{i}.xml" for i in range(7)]

    async def fake_resolve(_code):
        return mp, shard_urls

    monkeypatch.setattr(ob, "_resolve_shards", fake_resolve)

    dispatched: list = []
    monkeypatch.setattr(
        ob.sitemap_enumerate_shard,
        "apply_async",
        lambda args, kwargs=None, **opts: dispatched.append((args, kwargs, opts)),
    )
    redis = MagicMock()
    monkeypatch.setattr(
        "app.modules.scraper.pipeline.worker_log_relay._get_redis", lambda: redis
    )

    out = ob.sitemap_enumerate_marketplace.run("shop_x", max_urls=90_000)

    assert out["status"] == "sharded"
    # 7 subfiles / 3 per shard -> 3 children
    assert out["shards"] == 3
    assert len(dispatched) == 3
    args0, kwargs0, opts0 = dispatched[0]
    assert args0[0] == "shop_x"
    assert args0[1] == shard_urls[:3]
    assert kwargs0["run_id"] == out["run_id"]
    # never max_urls // shards: a shard keeps all of its subfiles' URLs
    assert kwargs0["max_urls"] == ob.ENUMERATE_SHARD_MAX_URLS == 150_000
    assert opts0["priority"] == 8
    # pending counter registered for the finisher aggregation
    redis.set.assert_called_once()
    assert redis.set.call_args.args[1] == 3


def test_enumerate_coordinator_flat_sitemap_runs_inline(monkeypatch) -> None:
    mp = SimpleNamespace(id=uuid4(), catalog_size_estimate=None)

    async def fake_resolve(_code):
        return mp, []  # no fan-out seam

    inline_calls: list = []

    async def fake_enumerate(code, max_urls, **kw):
        inline_calls.append((code, max_urls, kw))
        return {"status": "completed", "product_like": 5}

    monkeypatch.setattr(ob, "_resolve_shards", fake_resolve)
    monkeypatch.setattr(ob, "_enumerate", fake_enumerate)

    out = ob.sitemap_enumerate_marketplace.run("shop_flat", max_urls=1000)
    assert out["status"] == "completed"
    assert inline_calls and inline_calls[0][0] == "shop_flat"


def test_record_shard_done_aggregates_on_last(monkeypatch) -> None:
    redis = MagicMock()
    redis.decr.side_effect = [2, 1, 0]
    redis.hvals.return_value = [b"10", b"20", b"30"]
    monkeypatch.setattr(
        "app.modules.scraper.pipeline.worker_log_relay._get_redis", lambda: redis
    )
    assert ob._record_shard_done("s", "run", 0, 10) is None
    assert ob._record_shard_done("s", "run", 1, 20) is None
    assert ob._record_shard_done("s", "run", 2, 30) == 60


def test_scrape_stale_fanout_splits_free_and_paid_frontiers(monkeypatch) -> None:
    """Free (direct) shops get the full frontier; paid (proxy) shops only
    the value carriers within this tick's budget share; separate shards."""
    free_ids = [uuid4() for _ in range(10)]
    paid_ids = [uuid4() for _ in range(2)]
    session = MagicMock()
    session.execute.return_value.all.side_effect = [
        [("dead-shop-id",)],  # circuit breaker query
        [(i,) for i in free_ids],
        [(i,) for i in paid_ids],
    ]
    monkeypatch.setattr("app.database.sync_session_factory", lambda: session)
    monkeypatch.setattr(scraper_tasks, "_paid_quota_this_tick", lambda: 2)
    dispatched: list = []
    monkeypatch.setattr(
        scraper_tasks.scrape_listing_batch,
        "apply_async",
        lambda args, **opts: dispatched.append((args, opts)),
    )

    out = scraper_tasks.scrape_stale_fanout.run(shards=4, shard_size=3)

    assert (out["free"], out["paid"], out["paid_quota"]) == (10, 2, 2)
    assert out["due"] == 12 and out["dead_shops"] == 1
    assert out["shards_dispatched"] == 5  # 3+3+3+1 free, 2 paid
    assert all(opts["priority"] == 2 for _a, opts in dispatched)
    assert dispatched[-1][0][0] == [str(i) for i in paid_ids]
    free_call = session.execute.call_args_list[1]
    free_sql = str(free_call.args[0])
    # per-shop LATERAL with cap / probe, dead shops bound as a parameter
    assert "CROSS JOIN LATERAL" in free_sql and "LIMIT CASE WHEN m.id = ANY(:dead)" in free_sql
    assert free_call.args[1]["dead"] == ["dead-shop-id"]
    assert free_call.args[1]["cap"] == 3 and free_call.args[1]["total"] == 12
    paid_sql = str(session.execute.call_args_list[2].args[0].compile())
    assert "match_group_id IS NOT NULL" in paid_sql and "alerts" in paid_sql
    assert "LIMIT" in paid_sql


def test_scrape_stale_fanout_skips_paid_when_budget_spent(monkeypatch) -> None:
    session = MagicMock()
    session.execute.return_value.all.side_effect = [[], [(uuid4(),)]]
    monkeypatch.setattr("app.database.sync_session_factory", lambda: session)
    monkeypatch.setattr(scraper_tasks, "_paid_quota_this_tick", lambda: 0)
    monkeypatch.setattr(
        scraper_tasks.scrape_listing_batch, "apply_async", lambda args, **opts: None
    )
    out = scraper_tasks.scrape_stale_fanout.run(shards=1, shard_size=5)
    assert (out["free"], out["paid"]) == (1, 0)
    assert session.execute.call_count == 2  # breaker + free; paid not even queried


def test_paid_quota_spreads_remaining_allowance_over_ticks_left(monkeypatch) -> None:
    import calendar
    import time as _time

    monkeypatch.setattr(
        "app.modules.scraper.proxy_provider_limiter.budget_status_sync",
        lambda now=None: {"daily_allowance": 2400, "today_used": 1200},
    )
    # 12:00 UTC -> 24 of 48 ticks left -> (2400-1200)//24 = 50
    noon = calendar.timegm(_time.strptime("2026-09-19 12:00", "%Y-%m-%d %H:%M"))
    assert scraper_tasks._paid_quota_this_tick(noon) == 50
    monkeypatch.setattr(
        "app.modules.scraper.proxy_provider_limiter.budget_status_sync",
        lambda now=None: {"daily_allowance": None, "today_used": 0},
    )
    assert scraper_tasks._paid_quota_this_tick(noon) is None


def test_bulk_tasks_route_to_their_own_queue() -> None:
    from app.workers.celery_app import celery_app

    routes = celery_app.conf.task_routes
    for name in ("sitemap_enumerate_marketplace", "sitemap_enumerate_shard", "orchestrator_tick"):
        assert routes[name]["queue"] == "bulk", name
    # periodic ticks stay on the default queue
    assert "harvest_tick" not in routes and "scrape_stale_fanout" not in routes
