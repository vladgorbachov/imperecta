"""DB/network-free tests for discovery category_processor."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.modules.discovery import category_processor


@pytest.mark.asyncio
async def test_run_product_harvest_empty_window_when_list_shrank() -> None:
    mp = MagicMock()
    mp.id = "mp-id"
    mp.base_url = "https://shop.example/"
    pool = MagicMock()
    pool.scrape_page_for_analysis = AsyncMock()
    db = AsyncMock()

    async def filter_urls_by_role(urls, **kwargs):
        return urls, {"mode": "full"}

    async def save_product_urls(*args, **kwargs):
        return (0, 0, False)

    urls = [f"https://shop.example/c/{i}" for i in range(3)]
    total, next_index, more = await category_processor.run_product_harvest(
        mp,
        pool,
        db,
        urls,
        start_index=5,
        filter_urls_by_role=filter_urls_by_role,
        save_product_urls=save_product_urls,
    )

    assert (total, next_index, more) == (0, 0, False)
    pool.scrape_page_for_analysis.assert_not_awaited()


@pytest.mark.asyncio
async def test_run_product_harvest_convergence_streak_stops() -> None:
    mp = MagicMock()
    mp.id = "mp-id"
    mp.base_url = "https://shop.example/"
    pool = MagicMock()
    pool.scrape_page_for_analysis = AsyncMock(return_value=("<html></html>", MagicMock()))
    db = AsyncMock()

    async def filter_urls_by_role(urls, **kwargs):
        return [], {"mode": "full"}

    save_calls = 0

    async def save_product_urls(*args, **kwargs):
        nonlocal save_calls
        save_calls += 1
        return (0, 0, False)

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(
            "app.modules.discovery.category_processor.extract_links_from_repeated_structure",
            lambda soup, base, current: ["https://shop.example/p/1"],
        )
        monkeypatch.setattr(
            "app.modules.discovery.category_processor.detect_next_page",
            lambda soup, current: None,
        )
        urls = [f"https://shop.example/c/{i}" for i in range(5)]
        total, next_index, more = await category_processor.run_product_harvest(
            mp,
            pool,
            db,
            urls,
            filter_urls_by_role=filter_urls_by_role,
            save_product_urls=save_product_urls,
        )

    assert total == 0
    assert next_index == 0
    assert more is False
    assert save_calls == 0
    assert pool.scrape_page_for_analysis.await_count == category_processor.CATEGORY_CONVERGENCE_STREAK
