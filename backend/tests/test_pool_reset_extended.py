"""Tests for extended pool reset (blank slate behind data_firewall)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.modules.core.pool_maintenance import (
    PoolResetBlockedError,
    clear_product_pool_preserve_marketplaces,
)


def _mock_db() -> AsyncMock:
    db = AsyncMock()
    db.commit = AsyncMock()
    return db


def _count_side_effect(counts: dict[str, int]):
    """Map SELECT COUNT(*) table names to configured counts."""

    async def _execute(statement, *_args, **_kwargs):
        sql = str(statement)
        result = MagicMock()
        for table, value in counts.items():
            if f"FROM {table}" in sql:
                result.scalar.return_value = value
                return result
        result.scalar.return_value = 0
        return result

    return _execute


@pytest.mark.asyncio
async def test_reset_blocked_when_scrape_active() -> None:
    db = _mock_db()
    with patch(
        "app.modules.core.pool_maintenance._has_active_scrape_job",
        return_value=True,
    ):
        with pytest.raises(PoolResetBlockedError):
            await clear_product_pool_preserve_marketplaces(db)
    db.execute.assert_not_called()


@pytest.mark.asyncio
async def test_reset_truncates_pool() -> None:
    db = _mock_db()
    db.execute = AsyncMock(
        side_effect=_count_side_effect(
            {
                "fact_listing": 100,
                "dim_product": 90,
                "fact_price": 80,
                "scrape_logs": 200,
                "reject_data": 5,
            },
        ),
    )
    with patch(
        "app.modules.core.pool_maintenance._has_active_scrape_job",
        return_value=False,
    ):
        with patch("app.modules.core.pool_maintenance._refresh_mv") as mock_refresh:
            result = await clear_product_pool_preserve_marketplaces(db)

    sql = "\n".join(str(call.args[0]) for call in db.execute.call_args_list)
    assert "TRUNCATE TABLE reject_data" in sql
    assert "TRUNCATE TABLE fact_price" in sql
    assert "TRUNCATE TABLE fact_listing" in sql
    assert "TRUNCATE TABLE dim_product" in sql
    assert "TRUNCATE TABLE scrape_logs" in sql
    assert "DELETE FROM fact_listing" not in sql
    assert "DELETE FROM dim_product" not in sql
    assert "UPDATE dim_marketplace" in sql
    assert "ANALYZE fact_listing" in sql
    assert result["deleted_listings"] == 100
    assert result["deleted_reject_data"] == 5
    assert mock_refresh.call_count == 2


@pytest.mark.asyncio
async def test_reset_clears_discovery_cursors() -> None:
    db = _mock_db()
    db.execute = AsyncMock(side_effect=_count_side_effect({}))
    with patch(
        "app.modules.core.pool_maintenance._has_active_scrape_job",
        return_value=False,
    ):
        with patch("app.modules.core.pool_maintenance._refresh_mv"):
            await clear_product_pool_preserve_marketplaces(db)

    cursor_sql = next(
        str(call.args[0])
        for call in db.execute.call_args_list
        if "UPDATE dim_marketplace" in str(call.args[0])
    )
    for fragment in (
        "products_in_pool = 0",
        "sitemap_resume_offset = 0",
        "category_resume_index = 0",
        "recon_frontier_state = NULL",
        "discovered_category_urls = '[]'::jsonb",
        "last_sitemap_harvest_at = NULL",
        "last_category_recon_at = NULL",
        "last_discovery_at = NULL",
        "last_discovery_status = NULL",
        "discovery_error_count = 0",
    ):
        assert fragment in cursor_sql


@pytest.mark.asyncio
async def test_reset_keeps_market_data() -> None:
    db = _mock_db()
    db.execute = AsyncMock(side_effect=_count_side_effect({}))
    with patch(
        "app.modules.core.pool_maintenance._has_active_scrape_job",
        return_value=False,
    ):
        with patch("app.modules.core.pool_maintenance._refresh_mv"):
            await clear_product_pool_preserve_marketplaces(db)

    sql = "\n".join(str(call.args[0]) for call in db.execute.call_args_list)
    assert "fact_currency_rate" not in sql
    assert "fact_crypto_price" not in sql
    assert "fact_commodity_price" not in sql
    assert "dim_marketplace" in sql
    assert "TRUNCATE TABLE dim_marketplace" not in sql


@pytest.mark.asyncio
async def test_reset_idempotent() -> None:
    db = _mock_db()
    db.execute = AsyncMock(side_effect=_count_side_effect({}))
    with patch(
        "app.modules.core.pool_maintenance._has_active_scrape_job",
        return_value=False,
    ):
        with patch("app.modules.core.pool_maintenance._refresh_mv"):
            first = await clear_product_pool_preserve_marketplaces(db)
            second = await clear_product_pool_preserve_marketplaces(db)

    assert first == second == {
        "deleted_listings": 0,
        "deleted_products": 0,
        "deleted_prices": 0,
        "deleted_scrape_logs": 0,
        "deleted_reject_data": 0,
    }
    assert db.commit.await_count == 4

@pytest.mark.asyncio
async def test_reset_uses_non_concurrent_mv_refresh() -> None:
    db = _mock_db()
    db.execute = AsyncMock(side_effect=_count_side_effect({}))
    with patch(
        "app.modules.core.pool_maintenance._has_active_scrape_job",
        return_value=False,
    ):
        with patch("app.modules.core.pool_maintenance._refresh_mv") as mock_refresh:
            await clear_product_pool_preserve_marketplaces(db)

    assert mock_refresh.call_args_list[0].args[0] == "mv_daily_price_summary"
    assert mock_refresh.call_args_list[1].args[0] == "mv_marketplace_health"
