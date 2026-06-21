"""Tests for migration 026 JPY seed and clear-pool HTTP contract."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.modules.core.api_admin import clear_pool
from app.modules.core.pool_maintenance import clear_product_pool_preserve_marketplaces

MIGRATION_026 = Path(__file__).resolve().parents[1] / "alembic/versions/026_forex_nine_currency_allowlist.py"


def test_migration_026_jpy_inserts() -> None:
    """Migration 026 JPY INSERT must cover every NOT NULL dim_currency column."""
    text = MIGRATION_026.read_text(encoding="utf-8")
    assert "INSERT INTO dim_currency" in text
    assert "'JPY', 'Japanese Yen', '¥', 0, true" in text
    assert "is_active" in text
    assert "ON CONFLICT (currency_code) DO NOTHING" in text
    assert "DELETE FROM fact_currency_rate WHERE currency_code NOT IN" in text


def _mock_db() -> AsyncMock:
    db = AsyncMock()
    db.commit = AsyncMock()
    return db


def _count_side_effect(counts: dict[str, int]):
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
async def test_clear_pool_returns_200() -> None:
    """clear-pool endpoint returns 200 JSON even when MV refresh fails."""
    db = _mock_db()
    db.execute = AsyncMock(side_effect=_count_side_effect({}))

    with patch(
        "app.modules.core.pool_maintenance._has_active_scrape_job",
        return_value=False,
    ):
        with patch(
            "app.modules.core.pool_maintenance._refresh_mv",
            side_effect=RuntimeError("mv refresh boom"),
        ):
            body = await clear_pool(_current_user=MagicMock(), db=db)

    assert body["pool_cleared"] is True
    assert body["cursors_reset"] is True
    assert body["mv_refreshed"] is False
    assert body["post_maintenance_error"] is not None
    assert "mv refresh boom" in body["post_maintenance_error"]
    assert "time_ms" in body


@pytest.mark.asyncio
async def test_clear_pool_mv_failure_isolated() -> None:
    """MV/ANALYZE failure does not abort wipe; first commit still happens."""
    db = _mock_db()
    db.execute = AsyncMock(side_effect=_count_side_effect({"fact_listing": 3}))
    db.rollback = AsyncMock()

    with patch(
        "app.modules.core.pool_maintenance._has_active_scrape_job",
        return_value=False,
    ):
        with patch(
            "app.modules.core.pool_maintenance._refresh_mv",
            side_effect=OSError("disk full"),
        ):
            result = await clear_product_pool_preserve_marketplaces(db)

    assert result["pool_cleared"] is True
    assert result["fact_listing_deleted"] == 3
    assert result["mv_refreshed"] is False
    assert result["post_maintenance_error"] is not None
    assert db.commit.await_count == 1
    db.rollback.assert_awaited()


@pytest.mark.asyncio
async def test_clear_pool_blocked_still_409() -> None:
    """Active scrape guard fires before any wipe."""
    db = _mock_db()
    with patch(
        "app.modules.core.pool_maintenance._has_active_scrape_job",
        return_value=True,
    ):
        with pytest.raises(HTTPException) as exc_info:
            await clear_pool(_current_user=MagicMock(), db=db)
    assert exc_info.value.status_code == 409
