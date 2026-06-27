"""DB/network-free tests for discovery bfs_walker."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.modules.discovery import bfs_walker


@pytest.mark.asyncio
async def test_run_category_bfs_deadline_no_listings_exhausted() -> None:
    mp = MagicMock()
    mp.id = "mp-id"
    mp.base_url = "https://shop.example/"
    mp.recon_frontier_state = None
    mp.discovered_category_urls = []

    pool = MagicMock()
    pool.scrape_page_for_analysis = AsyncMock()
    db = AsyncMock()
    db.flush = AsyncMock()

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(
            "app.modules.discovery.bfs_walker.time.monotonic",
            lambda: 5000.0,
        )
        urls, exhausted = await bfs_walker.run_category_bfs(
            mp,
            pool,
            db,
            deadline_monotonic=4000.0,
        )

    assert (urls, exhausted) == ([], True)
    assert isinstance(mp.recon_frontier_state, dict)
    pool.scrape_page_for_analysis.assert_not_awaited()


@pytest.mark.asyncio
async def test_publish_replaces_discovered_category_urls() -> None:
    mp = MagicMock()
    mp.id = "mp-id"
    mp.base_url = "https://x/"
    mp.recon_frontier_state = {
        "queue": [],
        "visited": ["https://x/"],
        "listing_urls": [],
    }
    mp.discovered_category_urls = ["https://x/old"]
    mp.category_resume_index = 4

    pool = MagicMock()
    pool.scrape_page_for_analysis = AsyncMock(return_value=(None, None))
    db = AsyncMock()
    db.flush = AsyncMock()

    urls, exhausted = await bfs_walker.run_category_bfs(
        mp, pool, db, deadline_monotonic=None,
    )

    assert exhausted is False
    assert mp.category_resume_index == 0
    assert mp.discovered_category_urls == urls
