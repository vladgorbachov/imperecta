"""Pure-logic tests for discovery fetch_adapter (no DB/network)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from bs4 import BeautifulSoup

from app.models.dimensions import DimMarketplace
from app.modules.discovery import fetch_adapter
from app.modules.discovery.orchestrator import DiscoveryOrchestrator


def _marketplace(*, requires_js: bool = False, scrape_tier: int | None = 1) -> DimMarketplace:
    mp = MagicMock(spec=DimMarketplace)
    mp.requires_js = requires_js
    mp.scrape_tier = scrape_tier
    return mp


@pytest.mark.asyncio
async def test_fetch_page_requires_js_false_uses_layer_order_path() -> None:
    soup = BeautifulSoup("<html></html>", "html.parser")
    pool = MagicMock()
    pool.scrape_page_for_analysis = AsyncMock(return_value=("<html></html>", soup))

    html, result_soup = await fetch_adapter.fetch_page(
        pool,
        "https://shop.example/p/1",
        requires_js=False,
        scrape_tier=1,
        accept_language="en",
    )

    assert html == "<html></html>"
    assert result_soup is soup
    pool.scrape_page_for_analysis.assert_awaited_once_with(
        "https://shop.example/p/1",
        requires_js=False,
        scrape_tier=1,
        static_fetch=False,
        accept_language="en",
    )


@pytest.mark.asyncio
async def test_fetch_page_requires_js_true_forward_ready_stub() -> None:
    pool = MagicMock()
    pool.scrape_page_for_analysis = AsyncMock(return_value=(None, None))

    html, result_soup = await fetch_adapter.fetch_page(
        pool,
        "https://spa.example/p/1",
        requires_js=True,
        scrape_tier=1,
    )

    assert html is None
    assert result_soup is None
    pool.scrape_page_for_analysis.assert_awaited_once_with(
        "https://spa.example/p/1",
        requires_js=True,
        scrape_tier=1,
        static_fetch=False,
        accept_language=None,
    )


def test_fetch_params_from_marketplace_mirrors_listing_scrape_context() -> None:
    mp_false = _marketplace(requires_js=False, scrape_tier=1)
    assert fetch_adapter.fetch_params_from_marketplace(mp_false) == (False, 1)

    mp_js = _marketplace(requires_js=True, scrape_tier=1)
    assert fetch_adapter.fetch_params_from_marketplace(mp_js) == (True, 1)

    mp_none_tier = _marketplace(requires_js=False, scrape_tier=None)
    assert fetch_adapter.fetch_params_from_marketplace(mp_none_tier) == (False, 1)

    mp_zero_tier = _marketplace(requires_js=False, scrape_tier=0)
    assert fetch_adapter.fetch_params_from_marketplace(mp_zero_tier) == (False, 0)


@pytest.mark.asyncio
async def test_classify_and_resolve_url_threads_requires_js_into_fetch_adapter() -> None:
    soup = BeautifulSoup(
        '<html><head><link rel="canonical" href="/p/1"></head><body></body></html>',
        "html.parser",
    )
    pool = MagicMock()
    pool.scrape_page_for_analysis = AsyncMock(return_value=("<html></html>", soup))
    orchestrator = DiscoveryOrchestrator(db=MagicMock(), scraper_pool=pool)

    role, pool_url = await orchestrator._classify_and_resolve_url(
        "https://shop.example/p/1",
        requires_js=True,
        scrape_tier=1,
        marketplace_locale="en",
        accept_language="en-US,en;q=0.9",
    )

    assert role in {"product", "unknown", "listing", "hub"}
    assert pool_url
    pool.scrape_page_for_analysis.assert_awaited_once_with(
        "https://shop.example/p/1",
        requires_js=True,
        scrape_tier=1,
        static_fetch=False,
        accept_language="en-US,en;q=0.9",
    )
