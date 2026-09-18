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
    assert kwargs0["max_urls"] == 30_000
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


def test_scrape_stale_fanout_dispatches_priority_shards(monkeypatch) -> None:
    ids = [uuid4() for _ in range(10)]
    session = MagicMock()
    session.execute.return_value.all.return_value = [(i,) for i in ids]
    monkeypatch.setattr(
        "app.database.sync_session_factory", lambda: session
    )
    dispatched: list = []
    monkeypatch.setattr(
        scraper_tasks.scrape_listing_batch,
        "apply_async",
        lambda args, **opts: dispatched.append((args, opts)),
    )

    out = scraper_tasks.scrape_stale_fanout.run(shards=4, shard_size=3)

    assert out["due"] == 10
    assert out["shards_dispatched"] == 4  # 3+3+3+1
    assert all(opts["priority"] == 2 for _a, opts in dispatched)
    total_ids = sum(len(a[0]) for a, _o in dispatched)
    assert total_ids == 10
