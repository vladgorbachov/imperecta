"""Call scrape_diagnostics coroutine with AsyncMock DB (covers api query paths)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.modules.scraper import api as scraper_api


@pytest.mark.asyncio
async def test_scrape_diagnostics_executes_queries(monkeypatch):
    log_row = MagicMock()
    log_row.id = 1
    log_row.listing_id = MagicMock()
    log_row.status = "success"
    log_row.created_at = None
    log_row.error_message = None
    log_row.scraper_type = "httpx"

    cnt = MagicMock()
    cnt.scalar_one = lambda: 2

    logs = MagicMock()
    logs.scalars = lambda: MagicMock(all=lambda: [log_row])

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(side_effect=[cnt, logs])

    class _Cfg:
        decodo_enabled = False
        decodo_username = None
        decodo_password = None
        decodo_api_url = "https://example.com/"

    monkeypatch.setattr(scraper_api, "Settings", lambda: _Cfg())

    out = await scraper_api.scrape_diagnostics(db=mock_db, _current_user=MagicMock())
    assert out["listings_no_price_checked_24h"] == 2
    assert len(out["latest_scrape_logs_top5"]) == 1
    assert "decodo" in out


@pytest.mark.asyncio
async def test_admin_scrape_test_single_threadpool(monkeypatch):
    from uuid import uuid4

    from app.modules.scraper.scraper_pool import PoolScrapeResult
    from app.modules.scraper.service import GlobalScrapeService

    lid = uuid4()

    async def fake_run_in_threadpool(fn):
        return fn()

    monkeypatch.setattr("app.modules.scraper.api.run_in_threadpool", fake_run_in_threadpool)

    class Sess:
        def close(self):
            pass

    monkeypatch.setattr("app.modules.scraper.api.sync_session_factory", lambda: Sess())
    monkeypatch.setattr(
        GlobalScrapeService,
        "scrape_product",
        lambda self, _x: PoolScrapeResult(success=True, url="https://u"),
    )

    out = await scraper_api.admin_scrape_test_single(listing_id=lid, _current_user=MagicMock())
    assert out["result"]["success"] is True
