"""Cover remaining tasks.py branches (persist, _run_async, scrape impl)."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock
from uuid import uuid4

from app.modules.scraper import tasks as scraper_tasks
from app.modules.scraper.scraper_pool import PoolScrapeResult


def test_run_async_shutdown_asyncgen_error_ignored(monkeypatch):
    loop = asyncio.new_event_loop()

    async def boom():
        raise RuntimeError("asyncgen")

    loop.shutdown_asyncgens = boom  # type: ignore[method-assign]
    monkeypatch.setattr(asyncio, "new_event_loop", lambda: loop)
    monkeypatch.setattr(asyncio, "set_event_loop", lambda _x: None)

    async def coro():
        return 5

    assert scraper_tasks._run_async(coro()) == 5


def test_persist_technical_error_no_listing(monkeypatch):
    db = MagicMock()
    db.get.return_value = None
    monkeypatch.setattr(scraper_tasks, "sync_session_factory", lambda: db)
    scraper_tasks._persist_technical_error_log(uuid4(), "trace")
    db.add.assert_not_called()


def test_persist_technical_error_commit_failure(monkeypatch):
    listing = MagicMock()
    listing.id = uuid4()
    listing.marketplace_id = uuid4()
    listing.external_url = "https://x"

    db = MagicMock()
    db.get.return_value = listing
    db.commit.side_effect = RuntimeError("commit")
    monkeypatch.setattr(scraper_tasks, "sync_session_factory", lambda: db)
    scraper_tasks._persist_technical_error_log(listing.id, "trace")
    db.rollback.assert_called()


def test_scrape_pool_product_impl_success(monkeypatch):
    lid = uuid4()
    db = MagicMock()
    db.close = MagicMock()
    monkeypatch.setattr(scraper_tasks, "sync_session_factory", lambda: db)

    monkeypatch.setattr(
        "app.modules.scraper.service.GlobalScrapeService.scrape_product",
        lambda self, x: PoolScrapeResult(success=True, url="https://u", error=None),
    )

    out = scraper_tasks._scrape_pool_product_impl(str(lid))
    assert out["success"] is True and out["url"] == "https://u"
    db.close.assert_called()


def test_run_scrape_all_pool_impl_rollback_on_scrape(monkeypatch):
    lid = uuid4()
    listing = MagicMock()
    listing.external_url = "https://e.com"

    db = MagicMock()
    rows = MagicMock()
    rows.all.return_value = [(lid,)]
    db.execute.return_value = rows
    db.get.return_value = listing

    monkeypatch.setattr(scraper_tasks, "sync_session_factory", lambda: db)

    def boom(self, x):
        raise RuntimeError("scrape")

    monkeypatch.setattr(
        "app.modules.scraper.service.GlobalScrapeService.scrape_product",
        boom,
    )
    monkeypatch.setattr(scraper_tasks, "_persist_technical_error_log", lambda *a, **k: None)

    scraper_tasks._run_scrape_all_pool_impl()
    db.rollback.assert_called()


def test_run_scrape_all_impl_scrape_raises_and_rollback_fails(monkeypatch):
    lid = uuid4()
    listing = MagicMock()
    listing.external_url = "https://e.com"

    db = MagicMock()
    rows = MagicMock()
    rows.all.return_value = [(lid,)]
    db.execute.return_value = rows
    db.get.return_value = listing
    db.rollback.side_effect = RuntimeError("rollback failed")

    monkeypatch.setattr(scraper_tasks, "sync_session_factory", lambda: db)
    monkeypatch.setattr(
        "app.modules.scraper.service.GlobalScrapeService.scrape_product",
        lambda self, x: (_ for _ in ()).throw(RuntimeError("scrape")),
    )
    monkeypatch.setattr(scraper_tasks, "_persist_technical_error_log", lambda *a, **k: None)

    scraper_tasks._run_scrape_all_pool_impl()
    db.rollback.assert_called()


def test_persist_technical_error_rollback_in_except(monkeypatch):
    listing = MagicMock()
    listing.id = uuid4()
    listing.marketplace_id = uuid4()
    listing.external_url = "https://x"

    db = MagicMock()
    db.get.return_value = listing
    db.commit.side_effect = RuntimeError("commit")
    db.rollback.side_effect = RuntimeError("rollback too")

    monkeypatch.setattr(scraper_tasks, "sync_session_factory", lambda: db)
    scraper_tasks._persist_technical_error_log(listing.id, "tb")


def test_scrape_pool_product_outer_persist_failure(monkeypatch):
    monkeypatch.setattr(
        scraper_tasks,
        "_scrape_pool_product_impl",
        lambda _x: (_ for _ in ()).throw(RuntimeError("inner")),
    )
    monkeypatch.setattr(
        scraper_tasks,
        "_persist_technical_error_log",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("persist")),
    )
    out = scraper_tasks.scrape_pool_product.run(str(uuid4()))
    assert out.get("error") == "technical_error"
