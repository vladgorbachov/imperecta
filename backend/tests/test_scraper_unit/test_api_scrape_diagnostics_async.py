"""get_scrape_diagnostics and test_single_scrape with AsyncMock DB (contract paths)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.modules.scraper import api as scraper_api
from app.modules.scraper.scraper_pool import PoolScrapeResult
from app.modules.scraper.service import GlobalScrapeService


@pytest.mark.asyncio
async def test_get_scrape_diagnostics_executes_queries(monkeypatch):
    log_row = MagicMock()
    log_row.status = "success"
    log_row.url = "https://shop.example/p"
    log_row.price_found = 9.99
    log_row.duration_ms = 120

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(
        side_effect=[
            MagicMock(scalar_one=lambda: 42),
            MagicMock(scalar_one=lambda: 40),
            MagicMock(scalars=lambda: MagicMock(all=lambda: [log_row])),
            MagicMock(scalar_one_or_none=lambda: None),
        ]
    )

    async def fake_threadpool(fn, *args):
        if fn is scraper_api._decodo_tcp_reachable:
            return True
        return await fn(*args) if callable(fn) else fn

    monkeypatch.setattr(scraper_api, "run_in_threadpool", fake_threadpool)

    class _Cfg:
        decodo_enabled = True
        decodo_username = "u"
        decodo_password = "p"
        decodo_api_url = "https://scraper-api.decodo.com/v2/"

    monkeypatch.setattr(scraper_api, "Settings", lambda: _Cfg())

    out = await scraper_api.get_scrape_diagnostics(db=mock_db, _current_user=MagicMock())
    assert out["total_listings"] == 42
    assert out["with_price_last_24h"] == 40
    assert len(out["last_5_logs"]) == 1
    assert out["last_5_logs"][0]["status"] == "success"
    assert out["last_5_logs"][0]["url"] == "https://shop.example/p"
    assert out["last_5_logs"][0]["price_found"] == 9.99
    assert out["decodo_status"]["enabled"] is True
    assert out["decodo_status"]["healthy"] is True
    assert out["sample_result"] is None


@pytest.mark.asyncio
async def test_get_scrape_diagnostics_decodo_disabled_no_tcp(monkeypatch):
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(
        side_effect=[
            MagicMock(scalar_one=lambda: 0),
            MagicMock(scalar_one=lambda: 0),
            MagicMock(scalars=lambda: MagicMock(all=lambda: [])),
            MagicMock(scalar_one_or_none=lambda: None),
        ]
    )

    async def fake_threadpool(fn, *args):
        raise AssertionError("TCP probe must not run when Decodo is not configured")

    monkeypatch.setattr(scraper_api, "run_in_threadpool", fake_threadpool)

    class _Cfg:
        decodo_enabled = False
        decodo_username = ""
        decodo_password = ""
        decodo_api_url = "https://scraper-api.decodo.com/v2/"

    monkeypatch.setattr(scraper_api, "Settings", lambda: _Cfg())

    out = await scraper_api.get_scrape_diagnostics(db=mock_db, _current_user=MagicMock())
    assert out["decodo_status"]["enabled"] is False
    assert out["decodo_status"]["healthy"] is False


@pytest.mark.asyncio
async def test_sample_result_built_from_last_success():
    row = MagicMock()
    row.status = "success"
    row.url = "https://real/listing"
    row.price_found = 3.5
    row.duration_ms = 99
    row.scraper_type = "httpx"

    res = MagicMock()
    res.scalar_one_or_none = lambda: row

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=res)

    out = await scraper_api._sample_result_from_db(mock_db)
    assert out is not None
    assert out["success"] is True
    assert out["url"] == "https://real/listing"
    assert out["data"]["price"] == 3.5


@pytest.mark.asyncio
async def test_test_single_scrape_threadpool(monkeypatch):
    from uuid import uuid4

    lid = uuid4()

    async def fake_run_in_threadpool(fn):
        return fn()

    monkeypatch.setattr(scraper_api, "run_in_threadpool", fake_run_in_threadpool)

    class Sess:
        def close(self):
            pass

    monkeypatch.setattr(scraper_api, "sync_session_factory", lambda: Sess())
    monkeypatch.setattr(
        GlobalScrapeService,
        "scrape_product",
        lambda self, _x: PoolScrapeResult(success=True, url="https://u"),
    )

    out = await scraper_api.test_single_scrape(listing_id=lid, _current_user=MagicMock())
    assert out["result"]["success"] is True


@pytest.mark.asyncio
async def test_test_single_scrape_listing_not_found(monkeypatch):
    from uuid import uuid4

    lid = uuid4()

    async def fake_run_in_threadpool(fn):
        return fn()

    monkeypatch.setattr(scraper_api, "run_in_threadpool", fake_run_in_threadpool)

    class Sess:
        def close(self):
            pass

    monkeypatch.setattr(scraper_api, "sync_session_factory", lambda: Sess())
    monkeypatch.setattr(
        GlobalScrapeService,
        "scrape_product",
        lambda self, _x: PoolScrapeResult(success=False, url="", error="listing_not_found"),
    )

    out = await scraper_api.test_single_scrape(listing_id=lid, _current_user=MagicMock())
    assert out["result"]["success"] is False
    assert out["result"]["error"] == "listing_not_found"
