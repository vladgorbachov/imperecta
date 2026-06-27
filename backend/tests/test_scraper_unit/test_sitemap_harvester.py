"""Unit tests for discovery sitemap_harvester (DB/network-free)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.modules.discovery import cursor_store, sitemap_harvester
from app.models.dimensions import DimMarketplace
from app.modules.discovery.sitemap_harvester import (
    SITEMAP_BAD_HARVEST_RETRY_HOURS,
    SITEMAP_MIN_USEFUL_URLS,
    SITEMAP_STALE_DAYS,
)


def _make_marketplace(**overrides) -> DimMarketplace:
    defaults = dict(
        id=__import__("uuid").uuid4(),
        marketplace_code="test-mp",
        domain="test-mp.example",
        base_url="https://test-mp.example",
        is_active=True,
        locale=None,
        last_sitemap_harvest_at=None,
        sitemap_url=None,
        sitemap_bad_harvest_streak=0,
    )
    defaults.update(overrides)
    return DimMarketplace(**defaults)


@pytest.mark.asyncio
async def test_harvest_sitemap_useful_sets_fresh_cooldown_and_returns_products() -> None:
    mp = _make_marketplace()
    pool = MagicMock()
    pool.fetch_sitemap_candidates = AsyncMock(
        return_value=[f"https://test-mp.example/p/{i}" for i in range(12)],
    )
    db = AsyncMock()
    db.flush = AsyncMock()

    product_urls = [f"https://test-mp.example/product/{i}" for i in range(12)]

    async def fake_filter(urls, *, requires_js, scrape_tier, marketplace_locale=None):
        return product_urls, {"mode": "full", "accepted": len(product_urls)}

    result = await sitemap_harvester.harvest_sitemap(
        mp,
        pool,
        db,
        filter_urls_by_role=fake_filter,
    )

    assert result == product_urls
    assert len(result) >= SITEMAP_MIN_USEFUL_URLS
    assert cursor_store.get_last_sitemap_harvest_at(mp) is not None
    assert cursor_store.get_sitemap_url(mp) == "https://test-mp.example/sitemap.xml"
    pool.fetch_sitemap_candidates.assert_awaited_once_with(
        mp.base_url,
        marketplace_locale=mp.locale,
    )
    db.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_harvest_sitemap_not_useful_applies_retry_offset() -> None:
    mp = _make_marketplace(sitemap_url="https://test-mp.example/old-sitemap.xml")
    pool = MagicMock()
    pool.fetch_sitemap_candidates = AsyncMock(
        return_value=[f"https://test-mp.example/p/{i}" for i in range(5)],
    )
    db = AsyncMock()
    db.flush = AsyncMock()
    before = datetime.now(timezone.utc)

    few_products = [f"https://test-mp.example/product/{i}" for i in range(3)]

    async def fake_filter(urls, *, requires_js, scrape_tier, marketplace_locale=None):
        return few_products, {"mode": "full", "accepted": len(few_products)}

    result = await sitemap_harvester.harvest_sitemap(
        mp,
        pool,
        db,
        filter_urls_by_role=fake_filter,
    )

    assert result == few_products
    assert len(result) < SITEMAP_MIN_USEFUL_URLS
    assert cursor_store.get_sitemap_url(mp) == "https://test-mp.example/old-sitemap.xml"
    harvest_at = cursor_store.get_last_sitemap_harvest_at(mp)
    assert harvest_at is not None
    expected_offset = timedelta(
        days=SITEMAP_STALE_DAYS,
        hours=-SITEMAP_BAD_HARVEST_RETRY_HOURS,
    )
    assert harvest_at < before - expected_offset + timedelta(seconds=5)
    assert harvest_at > before - expected_offset - timedelta(seconds=5)


class TestSitemapHarvesterDefenceInDepth:
    """NODE 4: streak tracking + sitemap harvest alerts."""

    @staticmethod
    def _pool_and_db(raw_urls: list[str]) -> tuple[MagicMock, AsyncMock]:
        pool = MagicMock()
        pool.fetch_sitemap_candidates = AsyncMock(return_value=raw_urls)
        db = AsyncMock()
        db.flush = AsyncMock()
        return pool, db

    @pytest.mark.asyncio
    async def test_useful_harvest_resets_streak_no_alerts(self) -> None:
        mp = _make_marketplace(sitemap_bad_harvest_streak=2)
        pool, db = self._pool_and_db(
            [f"https://test-mp.example/p/{i}" for i in range(12)],
        )
        products = [f"https://test-mp.example/product/{i}" for i in range(12)]

        async def fake_filter(urls, *, requires_js, scrape_tier, marketplace_locale=None):
            return products, {"mode": "full", "accepted": len(products)}

        with patch(
            "app.modules.discovery.sitemap_harvester.emit_discovery_service_alert",
            new_callable=AsyncMock,
        ) as alert_mock:
            result = await sitemap_harvester.harvest_sitemap(
                mp, pool, db, filter_urls_by_role=fake_filter,
            )

        assert result == products
        assert cursor_store.get_sitemap_bad_harvest_streak(mp) == 0
        alert_mock.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_not_useful_increments_streak_alerts_on_third(self) -> None:
        mp = _make_marketplace()
        pool, db = self._pool_and_db(
            [f"https://test-mp.example/p/{i}" for i in range(5)],
        )
        few = [f"https://test-mp.example/product/{i}" for i in range(3)]

        async def fake_filter(urls, *, requires_js, scrape_tier, marketplace_locale=None):
            return few, {"mode": "full", "accepted": len(few)}

        with patch(
            "app.modules.discovery.sitemap_harvester.emit_discovery_service_alert",
            new_callable=AsyncMock,
        ) as alert_mock:
            await sitemap_harvester.harvest_sitemap(
                mp, pool, db, filter_urls_by_role=fake_filter,
            )
            await sitemap_harvester.harvest_sitemap(
                mp, pool, db, filter_urls_by_role=fake_filter,
            )
            await sitemap_harvester.harvest_sitemap(
                mp, pool, db, filter_urls_by_role=fake_filter,
            )

        assert cursor_store.get_sitemap_bad_harvest_streak(mp) == 3
        useful_false_calls = [
            c
            for c in alert_mock.await_args_list
            if len(c.args) >= 3 and c.args[2] == "sitemap_useful_false"
        ]
        assert len(useful_false_calls) == 1
        assert useful_false_calls[0].kwargs["context"]["streak"] == 3

    @pytest.mark.asyncio
    async def test_sitemap_raw_empty_alerts_when_prior_harvest_known(self) -> None:
        mp = _make_marketplace(
            last_sitemap_harvest_at=datetime.now(timezone.utc),
        )
        pool, db = self._pool_and_db([])

        async def fake_filter(urls, *, requires_js, scrape_tier, marketplace_locale=None):
            return [], {"mode": "empty"}

        with patch(
            "app.modules.discovery.sitemap_harvester.emit_discovery_service_alert",
            new_callable=AsyncMock,
        ) as alert_mock:
            await sitemap_harvester.harvest_sitemap(
                mp, pool, db, filter_urls_by_role=fake_filter,
            )

        raw_empty_calls = [
            c
            for c in alert_mock.await_args_list
            if len(c.args) >= 3 and c.args[2] == "sitemap_raw_empty"
        ]
        assert len(raw_empty_calls) == 1

    @pytest.mark.asyncio
    async def test_sitemap_raw_empty_no_alert_on_first_harvest(self) -> None:
        mp = _make_marketplace(
            last_sitemap_harvest_at=None,
            sitemap_url=None,
        )
        pool, db = self._pool_and_db([])

        async def fake_filter(urls, *, requires_js, scrape_tier, marketplace_locale=None):
            return [], {"mode": "empty"}

        with patch(
            "app.modules.discovery.sitemap_harvester.emit_discovery_service_alert",
            new_callable=AsyncMock,
        ) as alert_mock:
            await sitemap_harvester.harvest_sitemap(
                mp, pool, db, filter_urls_by_role=fake_filter,
            )

        raw_empty_calls = [
            c
            for c in alert_mock.await_args_list
            if len(c.args) >= 3 and c.args[2] == "sitemap_raw_empty"
        ]
        assert len(raw_empty_calls) == 0

    @pytest.mark.asyncio
    async def test_sitemap_reject_sample_alerts_when_mode_and_raw_threshold(self) -> None:
        mp = _make_marketplace()
        pool, db = self._pool_and_db(
            [f"https://test-mp.example/p/{i}" for i in range(120)],
        )

        async def fake_filter(urls, *, requires_js, scrape_tier, marketplace_locale=None):
            return [], {
                "mode": "reject_sample",
                "sample_product_ratio": 0.0,
                "accepted": 0,
            }

        with patch(
            "app.modules.discovery.sitemap_harvester.emit_discovery_service_alert",
            new_callable=AsyncMock,
        ) as alert_mock:
            await sitemap_harvester.harvest_sitemap(
                mp, pool, db, filter_urls_by_role=fake_filter,
            )

        reject_calls = [
            c
            for c in alert_mock.await_args_list
            if len(c.args) >= 3 and c.args[2] == "sitemap_reject_sample"
        ]
        assert len(reject_calls) == 1
        assert reject_calls[0].kwargs["context"]["raw"] == 120

    @pytest.mark.asyncio
    async def test_sitemap_reject_sample_no_alert_on_full_mode(self) -> None:
        mp = _make_marketplace()
        pool, db = self._pool_and_db(
            [f"https://test-mp.example/p/{i}" for i in range(120)],
        )
        products = [f"https://test-mp.example/product/{i}" for i in range(12)]

        async def fake_filter(urls, *, requires_js, scrape_tier, marketplace_locale=None):
            return products, {"mode": "full", "accepted": len(products)}

        with patch(
            "app.modules.discovery.sitemap_harvester.emit_discovery_service_alert",
            new_callable=AsyncMock,
        ) as alert_mock:
            result = await sitemap_harvester.harvest_sitemap(
                mp, pool, db, filter_urls_by_role=fake_filter,
            )

        assert len(result) >= SITEMAP_MIN_USEFUL_URLS
        reject_calls = [
            c
            for c in alert_mock.await_args_list
            if len(c.args) >= 3 and c.args[2] == "sitemap_reject_sample"
        ]
        assert len(reject_calls) == 0
