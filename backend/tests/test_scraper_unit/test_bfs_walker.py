"""DB/network-free tests for discovery bfs_walker."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.modules.discovery import bfs_walker, cursor_store


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


@pytest.mark.asyncio
async def test_run_category_bfs_corrupt_frontier_emits_alert_and_proceeds() -> None:
    from uuid import uuid4

    mp = MagicMock()
    mp.id = uuid4()
    mp.base_url = "https://shop.example"
    mp.recon_frontier_state = {
        "queue": [["bad-item"]],
        "visited": [],
        "listing_urls": [],
    }
    mp.category_resume_index = 3
    mp.discovered_category_urls = []

    pool = MagicMock()
    pool.scrape_page_for_analysis = AsyncMock(return_value=(None, None))
    db = AsyncMock()
    db.flush = AsyncMock()

    with patch(
        "app.modules.discovery.bfs_walker.emit_discovery_service_alert",
        new_callable=AsyncMock,
    ) as alert_mock:
        urls, exhausted = await bfs_walker.run_category_bfs(
            mp, pool, db, deadline_monotonic=None,
        )

    alert_mock.assert_awaited_once()
    assert alert_mock.await_args.args[2] == "frontier_deserialize_failed"
    assert mp.category_resume_index == 0
    assert exhausted is False


@pytest.mark.asyncio
async def test_run_category_bfs_valid_frontier_resume_no_alert() -> None:
    mp = MagicMock()
    mp.id = "mp-id"
    mp.base_url = "https://shop.example"
    mp.recon_frontier_state = {
        "queue": [],
        "visited": ["https://shop.example"],
        "listing_urls": [],
    }
    mp.discovered_category_urls = []
    mp.category_resume_index = 0

    pool = MagicMock()
    pool.scrape_page_for_analysis = AsyncMock(return_value=(None, None))
    db = AsyncMock()
    db.flush = AsyncMock()

    with patch(
        "app.modules.discovery.bfs_walker.emit_discovery_service_alert",
        new_callable=AsyncMock,
    ) as alert_mock:
        urls, exhausted = await bfs_walker.run_category_bfs(
            mp, pool, db, deadline_monotonic=None,
        )

    alert_mock.assert_not_awaited()
    assert exhausted is False


class TestBfsWalkerDefenceInDepth:
    """NODE 6: phase1 exhausted streak + budget alerts."""

    @staticmethod
    def _mp_with_streak(streak: int = 0) -> MagicMock:
        mp = MagicMock()
        mp.id = "mp-id"
        mp.base_url = "https://shop.example/"
        mp.recon_frontier_state = None
        mp.discovered_category_urls = []
        mp.phase1_exhausted_streak = streak
        return mp

    @pytest.mark.asyncio
    async def test_phase1_budget_exhausted_no_publish_emits_warning(self) -> None:
        mp = self._mp_with_streak()
        pool = MagicMock()
        pool.scrape_page_for_analysis = AsyncMock()
        db = AsyncMock()
        db.flush = AsyncMock()

        with (
            pytest.MonkeyPatch.context() as monkeypatch,
            patch(
                "app.modules.discovery.bfs_walker.emit_discovery_service_alert",
                new_callable=AsyncMock,
            ) as alert_mock,
        ):
            monkeypatch.setattr(
                "app.modules.discovery.bfs_walker.time.monotonic",
                lambda: 5000.0,
            )
            urls, exhausted = await bfs_walker.run_category_bfs(
                mp, pool, db, deadline_monotonic=4000.0,
            )

        assert (urls, exhausted) == ([], True)
        warning_calls = [
            c
            for c in alert_mock.await_args_list
            if len(c.args) >= 3 and c.args[2] == "phase1_budget_exhausted_no_publish"
        ]
        assert len(warning_calls) == 1
        assert cursor_store.get_phase1_exhausted_streak(mp) == 1

    @pytest.mark.asyncio
    async def test_phase1_repeated_exhausted_emits_info_on_third(self) -> None:
        mp = self._mp_with_streak(2)
        pool = MagicMock()
        pool.scrape_page_for_analysis = AsyncMock()
        db = AsyncMock()
        db.flush = AsyncMock()

        with (
            pytest.MonkeyPatch.context() as monkeypatch,
            patch(
                "app.modules.discovery.bfs_walker.emit_discovery_service_alert",
                new_callable=AsyncMock,
            ) as alert_mock,
        ):
            monkeypatch.setattr(
                "app.modules.discovery.bfs_walker.time.monotonic",
                lambda: 5000.0,
            )
            await bfs_walker.run_category_bfs(
                mp, pool, db, deadline_monotonic=4000.0,
            )

        assert cursor_store.get_phase1_exhausted_streak(mp) == 3
        repeated_calls = [
            c
            for c in alert_mock.await_args_list
            if len(c.args) >= 3 and c.args[2] == "phase1_repeated_exhausted"
        ]
        assert len(repeated_calls) == 1
        assert repeated_calls[0].kwargs["context"]["streak"] == 3

    @pytest.mark.asyncio
    async def test_phase1_publish_resets_streak_no_exhausted_warning(self) -> None:
        mp = self._mp_with_streak(2)
        mp.recon_frontier_state = {
            "queue": [["https://shop.example/cat", 1]],
            "visited": ["https://shop.example/"],
            "listing_urls": [],
        }
        pool = MagicMock()
        pool.scrape_page_for_analysis = AsyncMock(
            return_value=("<html></html>", MagicMock()),
        )
        db = AsyncMock()
        db.flush = AsyncMock()

        with (
            pytest.MonkeyPatch.context() as monkeypatch,
            patch(
                "app.modules.discovery.bfs_walker.emit_discovery_service_alert",
                new_callable=AsyncMock,
            ) as alert_mock,
            patch(
                "app.modules.discovery.bfs_walker.classifier_adapter.classify_page_role",
                return_value="listing",
            ),
            patch(
                "app.modules.discovery.bfs_walker.extract_internal_links_all",
                return_value=[],
            ),
        ):
            monkeypatch.setattr(
                "app.modules.discovery.bfs_walker.time.monotonic",
                lambda: 1000.0,
            )
            urls, exhausted = await bfs_walker.run_category_bfs(
                mp, pool, db, deadline_monotonic=None,
            )

        assert exhausted is False
        assert len(urls) > 0
        assert cursor_store.get_phase1_exhausted_streak(mp) == 0
        exhausted_calls = [
            c
            for c in alert_mock.await_args_list
            if len(c.args) >= 3
            and c.args[2] in (
                "phase1_budget_exhausted_no_publish",
                "phase1_repeated_exhausted",
            )
        ]
        assert len(exhausted_calls) == 0

    @pytest.mark.asyncio
    async def test_phase1_deadline_with_listings_publishes_and_resets_streak(
        self,
    ) -> None:
        mp = self._mp_with_streak(2)
        mp.recon_frontier_state = {
            "queue": [["https://shop.example/cat", 0]],
            "visited": ["https://shop.example/cat"],
            "listing_urls": [],
        }
        pool = MagicMock()
        pool.scrape_page_for_analysis = AsyncMock(
            return_value=("<html></html>", MagicMock()),
        )
        db = AsyncMock()
        db.flush = AsyncMock()
        times = iter([3000.0, 5000.0])

        with (
            pytest.MonkeyPatch.context() as monkeypatch,
            patch(
                "app.modules.discovery.bfs_walker.emit_discovery_service_alert",
                new_callable=AsyncMock,
            ) as alert_mock,
            patch(
                "app.modules.discovery.bfs_walker.classifier_adapter.classify_page_role",
                return_value="listing",
            ),
            patch(
                "app.modules.discovery.bfs_walker.extract_internal_links_all",
                return_value=[],
            ),
        ):
            monkeypatch.setattr(
                "app.modules.discovery.bfs_walker.time.monotonic",
                lambda: next(times, 5000.0),
            )
            urls, exhausted = await bfs_walker.run_category_bfs(
                mp, pool, db, deadline_monotonic=4000.0,
            )

        assert exhausted is False
        assert len(urls) > 0
        assert cursor_store.get_phase1_exhausted_streak(mp) == 0
        warning_calls = [
            c
            for c in alert_mock.await_args_list
            if len(c.args) >= 3 and c.args[2] == "phase1_budget_exhausted_no_publish"
        ]
        assert len(warning_calls) == 0
