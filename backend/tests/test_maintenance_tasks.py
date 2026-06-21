"""Tests for materialized-view maintenance (D-DISKFULL fix)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.workers import maintenance_tasks as mt


def test_refresh_uses_non_concurrent() -> None:
    cursor = MagicMock()
    raw = MagicMock()
    raw.cursor.return_value = cursor

    with patch.object(mt, "sync_engine") as mock_engine:
        mock_engine.raw_connection.return_value = raw
        mt._refresh_mv("mv_daily_price_summary")

    executed = [call.args[0] for call in cursor.execute.call_args_list]
    refresh_statements = [sql for sql in executed if "REFRESH MATERIALIZED VIEW" in sql]
    assert len(refresh_statements) == 1
    assert "CONCURRENTLY" not in refresh_statements[0]
    assert refresh_statements[0] == "REFRESH MATERIALIZED VIEW mv_daily_price_summary"


def test_refresh_sets_temp_file_limit() -> None:
    cursor = MagicMock()
    raw = MagicMock()
    raw.cursor.return_value = cursor

    with patch.object(mt, "Settings") as mock_settings_cls:
        mock_settings_cls.return_value.mv_refresh_temp_file_limit_mb = 256
        mock_settings_cls.return_value.mv_refresh_work_mem_mb = 64
        with patch.object(mt, "sync_engine") as mock_engine:
            mock_engine.raw_connection.return_value = raw
            mt._refresh_mv("mv_marketplace_health")

    executed = [call.args[0] for call in cursor.execute.call_args_list]
    assert executed[0] == "SET temp_file_limit = 262144"
    assert executed[1] == "SET work_mem = '64MB'"
    assert executed[2] == "REFRESH MATERIALIZED VIEW mv_marketplace_health"


def test_refresh_skips_during_active_scrape() -> None:
    with patch.object(mt, "_has_active_scrape_job", return_value=True):
        with patch.object(mt, "_refresh_one_mv") as mock_refresh:
            mt.refresh_materialized_views()
    mock_refresh.assert_not_called()


def test_refresh_failure_isolated() -> None:
    calls: list[str] = []

    def _side_effect(mv_name: str) -> None:
        calls.append(mv_name)
        if mv_name == "mv_daily_price_summary":
            raise RuntimeError("disk full")

    with patch.object(mt, "_has_active_scrape_job", return_value=False):
        with patch.object(mt, "_refresh_mv", side_effect=_side_effect):
            with patch.object(mt, "capture_exception_if_initialized") as mock_sentry:
                mt.refresh_materialized_views()

    assert calls == ["mv_daily_price_summary", "mv_marketplace_health"]
    mock_sentry.assert_called_once()


def test_refresh_mv_rejects_unknown_name() -> None:
    with pytest.raises(ValueError, match="unsupported materialized view"):
        mt._refresh_mv("mv_unknown")
