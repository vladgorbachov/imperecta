"""DB/network-free tests for discovery category_processor."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

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


def _harvest_fixtures() -> tuple[MagicMock, MagicMock, AsyncMock]:
    mp = MagicMock()
    mp.id = "mp-id"
    mp.base_url = "https://shop.example/"
    mp.locale = None
    mp.requires_js = False
    mp.scrape_tier = 1
    pool = MagicMock()
    pool.scrape_page_for_analysis = AsyncMock(
        return_value=("<html></html>", MagicMock()),
    )
    db = AsyncMock()
    return mp, pool, db


class TestCategoryProcessorDefenceInDepth:
    """NODE 5: phase2 zero-yield and converged-empty alerts."""

    @pytest.mark.asyncio
    async def test_phase2_zero_yield_emits_warning(self) -> None:
        mp, pool, db = _harvest_fixtures()
        urls = [f"https://shop.example/c/{i}" for i in range(4)]

        async def filter_urls_by_role(gated, **kwargs):
            return gated, {"mode": "full"}

        async def save_product_urls(*args, **kwargs):
            return (0, len(args[1]), False)

        with (
            pytest.MonkeyPatch.context() as monkeypatch,
            patch(
                "app.modules.discovery.category_processor.emit_discovery_service_alert",
                new_callable=AsyncMock,
            ) as alert_mock,
        ):
            monkeypatch.setattr(
                "app.modules.discovery.category_processor.extract_links_from_repeated_structure",
                lambda soup, base, current: ["https://shop.example/p/1"],
            )
            monkeypatch.setattr(
                "app.modules.discovery.category_processor.detect_next_page",
                lambda soup, current: None,
            )
            total, _, _ = await category_processor.run_product_harvest(
                mp,
                pool,
                db,
                urls,
                filter_urls_by_role=filter_urls_by_role,
                save_product_urls=save_product_urls,
            )

        assert total == 0
        zero_yield_calls = [
            c
            for c in alert_mock.await_args_list
            if len(c.args) >= 3 and c.args[2] == "phase2_zero_yield"
        ]
        assert len(zero_yield_calls) == 1
        assert zero_yield_calls[0].kwargs["context"]["candidate_urls_extracted"] > 0

    @pytest.mark.asyncio
    async def test_phase2_converged_empty_emits_info(self) -> None:
        mp, pool, db = _harvest_fixtures()
        urls = [f"https://shop.example/c/{i}" for i in range(5)]

        async def filter_urls_by_role(gated, **kwargs):
            return [], {"mode": "full"}

        async def save_product_urls(*args, **kwargs):
            return (0, 0, False)

        with (
            pytest.MonkeyPatch.context() as monkeypatch,
            patch(
                "app.modules.discovery.category_processor.emit_discovery_service_alert",
                new_callable=AsyncMock,
            ) as alert_mock,
        ):
            monkeypatch.setattr(
                "app.modules.discovery.category_processor.extract_links_from_repeated_structure",
                lambda soup, base, current: [],
            )
            monkeypatch.setattr(
                "app.modules.discovery.category_processor.extract_product_links",
                lambda soup, base: [],
            )
            monkeypatch.setattr(
                "app.modules.discovery.category_processor.detect_next_page",
                lambda soup, current: None,
            )
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
        converged_calls = [
            c
            for c in alert_mock.await_args_list
            if len(c.args) >= 3 and c.args[2] == "phase2_converged_empty"
        ]
        assert len(converged_calls) == 1
        zero_yield_calls = [
            c
            for c in alert_mock.await_args_list
            if len(c.args) >= 3 and c.args[2] == "phase2_zero_yield"
        ]
        assert len(zero_yield_calls) == 0

    @pytest.mark.asyncio
    async def test_phase2_precedence_zero_yield_over_converged_empty(self) -> None:
        mp, pool, db = _harvest_fixtures()
        urls = [f"https://shop.example/c/{i}" for i in range(5)]

        async def filter_urls_by_role(gated, **kwargs):
            return [], {"mode": "full"}

        async def save_product_urls(*args, **kwargs):
            return (0, 0, False)

        with (
            pytest.MonkeyPatch.context() as monkeypatch,
            patch(
                "app.modules.discovery.category_processor.emit_discovery_service_alert",
                new_callable=AsyncMock,
            ) as alert_mock,
        ):
            monkeypatch.setattr(
                "app.modules.discovery.category_processor.extract_links_from_repeated_structure",
                lambda soup, base, current: ["https://shop.example/p/1"],
            )
            monkeypatch.setattr(
                "app.modules.discovery.category_processor.detect_next_page",
                lambda soup, current: None,
            )
            await category_processor.run_product_harvest(
                mp,
                pool,
                db,
                urls,
                filter_urls_by_role=filter_urls_by_role,
                save_product_urls=save_product_urls,
            )

        zero_yield_calls = [
            c
            for c in alert_mock.await_args_list
            if len(c.args) >= 3 and c.args[2] == "phase2_zero_yield"
        ]
        converged_calls = [
            c
            for c in alert_mock.await_args_list
            if len(c.args) >= 3 and c.args[2] == "phase2_converged_empty"
        ]
        assert len(zero_yield_calls) == 1
        assert len(converged_calls) == 0

    @pytest.mark.asyncio
    async def test_phase2_normal_harvest_no_alerts(self) -> None:
        mp, pool, db = _harvest_fixtures()
        urls = [f"https://shop.example/c/{i}" for i in range(3)]

        async def filter_urls_by_role(gated, **kwargs):
            return gated, {"mode": "full"}

        async def save_product_urls(*args, **kwargs):
            return (len(args[1]), len(args[1]), False)

        with (
            pytest.MonkeyPatch.context() as monkeypatch,
            patch(
                "app.modules.discovery.category_processor.emit_discovery_service_alert",
                new_callable=AsyncMock,
            ) as alert_mock,
        ):
            monkeypatch.setattr(
                "app.modules.discovery.category_processor.extract_links_from_repeated_structure",
                lambda soup, base, current: ["https://shop.example/p/1"],
            )
            monkeypatch.setattr(
                "app.modules.discovery.category_processor.detect_next_page",
                lambda soup, current: None,
            )
            total, _, _ = await category_processor.run_product_harvest(
                mp,
                pool,
                db,
                urls,
                filter_urls_by_role=filter_urls_by_role,
                save_product_urls=save_product_urls,
            )

        assert total > 0
        alert_mock.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_phase2_below_threshold_no_zero_yield(self) -> None:
        mp, pool, db = _harvest_fixtures()
        urls = [f"https://shop.example/c/{i}" for i in range(2)]

        async def filter_urls_by_role(gated, **kwargs):
            return gated, {"mode": "full"}

        async def save_product_urls(*args, **kwargs):
            return (0, len(args[1]), False)

        with (
            pytest.MonkeyPatch.context() as monkeypatch,
            patch(
                "app.modules.discovery.category_processor.emit_discovery_service_alert",
                new_callable=AsyncMock,
            ) as alert_mock,
        ):
            monkeypatch.setattr(
                "app.modules.discovery.category_processor.extract_links_from_repeated_structure",
                lambda soup, base, current: ["https://shop.example/p/1"],
            )
            monkeypatch.setattr(
                "app.modules.discovery.category_processor.detect_next_page",
                lambda soup, current: None,
            )
            total, _, _ = await category_processor.run_product_harvest(
                mp,
                pool,
                db,
                urls,
                filter_urls_by_role=filter_urls_by_role,
                save_product_urls=save_product_urls,
            )

        assert total == 0
        zero_yield_calls = [
            c
            for c in alert_mock.await_args_list
            if len(c.args) >= 3 and c.args[2] == "phase2_zero_yield"
        ]
        assert len(zero_yield_calls) == 0


class TestFetchEmptySoupSpike:
    """NODE 7: post-loop fetch empty soup rate alerts."""

    @pytest.mark.asyncio
    async def test_harvest_spike_emits_warning_at_high_empty_rate(self) -> None:
        mp, pool, db = _harvest_fixtures()
        pool.scrape_page_for_analysis = AsyncMock(return_value=(None, None))
        urls = [f"https://shop.example/c/{i}" for i in range(5)]

        async def filter_urls_by_role(gated, **kwargs):
            return gated, {"mode": "full"}

        async def save_product_urls(*args, **kwargs):
            return (0, 0, False)

        with (
            patch(
                "app.modules.discovery.alerting.emit_discovery_service_alert",
                new_callable=AsyncMock,
            ) as alert_mock,
            pytest.MonkeyPatch.context() as monkeypatch,
        ):
            monkeypatch.setattr(
                category_processor,
                "CATEGORY_CONVERGENCE_STREAK",
                10,
            )
            await category_processor.run_product_harvest(
                mp,
                pool,
                db,
                urls,
                filter_urls_by_role=filter_urls_by_role,
                save_product_urls=save_product_urls,
            )

        spike_calls = [
            c
            for c in alert_mock.await_args_list
            if len(c.args) >= 3 and c.args[2] == "fetch_empty_soup_spike"
        ]
        assert len(spike_calls) == 1
        ctx = spike_calls[0].kwargs["context"]
        assert ctx["phase"] == "category_harvest"
        assert ctx["total_fetches"] == 5
        assert ctx["empty_rate"] == 1.0

    @pytest.mark.asyncio
    async def test_harvest_no_spike_below_min_samples(self) -> None:
        mp, pool, db = _harvest_fixtures()
        pool.scrape_page_for_analysis = AsyncMock(return_value=(None, None))
        urls = [f"https://shop.example/c/{i}" for i in range(3)]

        async def filter_urls_by_role(gated, **kwargs):
            return gated, {"mode": "full"}

        async def save_product_urls(*args, **kwargs):
            return (0, 0, False)

        with patch(
            "app.modules.discovery.alerting.emit_discovery_service_alert",
            new_callable=AsyncMock,
        ) as alert_mock:
            await category_processor.run_product_harvest(
                mp,
                pool,
                db,
                urls,
                filter_urls_by_role=filter_urls_by_role,
                save_product_urls=save_product_urls,
            )

        spike_calls = [
            c
            for c in alert_mock.await_args_list
            if len(c.args) >= 3 and c.args[2] == "fetch_empty_soup_spike"
        ]
        assert len(spike_calls) == 0

    @pytest.mark.asyncio
    async def test_harvest_no_spike_on_normal_run(self) -> None:
        mp, pool, db = _harvest_fixtures()
        urls = [f"https://shop.example/c/{i}" for i in range(3)]

        async def filter_urls_by_role(gated, **kwargs):
            return gated, {"mode": "full"}

        async def save_product_urls(*args, **kwargs):
            return (len(args[1]), len(args[1]), False)

        with (
            pytest.MonkeyPatch.context() as monkeypatch,
            patch(
                "app.modules.discovery.alerting.emit_discovery_service_alert",
                new_callable=AsyncMock,
            ) as alert_mock,
        ):
            monkeypatch.setattr(
                "app.modules.discovery.category_processor.extract_links_from_repeated_structure",
                lambda soup, base, current: ["https://shop.example/p/1"],
            )
            monkeypatch.setattr(
                "app.modules.discovery.category_processor.detect_next_page",
                lambda soup, current: None,
            )
            total, _, _ = await category_processor.run_product_harvest(
                mp,
                pool,
                db,
                urls,
                filter_urls_by_role=filter_urls_by_role,
                save_product_urls=save_product_urls,
            )

        assert total > 0
        spike_calls = [
            c
            for c in alert_mock.await_args_list
            if len(c.args) >= 3 and c.args[2] == "fetch_empty_soup_spike"
        ]
        assert len(spike_calls) == 0
