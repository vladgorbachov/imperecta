"""DB-free tests for retention seam 5 (#19-22 bypass closure)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from app.modules.persist.retention import (
    RetentionTableNotWhitelistedError,
    assert_retention_table_whitelisted,
    retention_cutoff,
    retention_delete_table,
)
from app.modules.persist.retention_config import RETENTION_TABLES

BACKEND_ROOT = Path(__file__).resolve().parents[2]


def test_invariant_11_rejects_user_and_analytic_tables() -> None:
    for table in ("ai_chat_messages", "alert_events"):
        assert table not in RETENTION_TABLES
        with pytest.raises(RetentionTableNotWhitelistedError, match=table):
            assert_retention_table_whitelisted(table)


def test_cleanup_tasks_module_removed() -> None:
    assert not (BACKEND_ROOT / "app/workers/cleanup_tasks.py").exists()


def test_scheduler_has_no_cleanup_old_data_beat() -> None:
    source = (BACKEND_ROOT / "app/workers/scheduler.py").read_text(encoding="utf-8")
    assert "cleanup_old_data" not in source
    assert "ensure_fact_price_partitions" not in source
    assert "refresh_materialized_views" not in source
    assert "run_service_data_retention" in source


def test_celery_include_has_no_cleanup_tasks() -> None:
    source = (BACKEND_ROOT / "app/workers/celery_app.py").read_text(encoding="utf-8")
    assert "cleanup_tasks" not in source


@patch("app.modules.persist.retention.write_sync")
@patch("app.modules.persist.retention.authorize_retention_delete")
@patch("app.modules.persist.retention.sync_session_factory")
def test_scrape_logs_retention_uses_14_day_window(
    mock_session_factory,
    mock_authorize,
    mock_write_sync,
) -> None:
    from app.modules.data_firewall.firewall import FirewallOutcome
    from unittest.mock import MagicMock

    now = datetime(2026, 6, 17, 12, 0, 0, tzinfo=timezone.utc)
    expected_cutoff = now - timedelta(days=14)
    mock_authorize.return_value = FirewallOutcome(
        passed=True,
        reject_reason=None,
        failed_rules=[],
        forced_log_status=None,
        page_role_verdict=None,
        notes={},
        signed_record=MagicMock(),
    )
    mock_write_sync.return_value = MagicMock(ok=True, rows_affected=0)

    session = MagicMock()
    mock_cm = MagicMock()
    mock_cm.__enter__.return_value = session
    mock_cm.__exit__.return_value = False
    mock_session_factory.return_value = mock_cm

    retention_delete_table("scrape_logs", now=now)

    fields = mock_authorize.call_args.kwargs["fields"]
    assert fields["cutoff_column"] == "created_at"
    assert fields["cutoff"] == expected_cutoff.isoformat()


@patch("app.modules.persist.retention.write_sync")
@patch("app.modules.persist.retention.authorize_retention_delete")
@patch("app.modules.persist.retention.sync_session_factory")
def test_api_logs_retention_uses_60_day_window(
    mock_session_factory,
    mock_authorize,
    mock_write_sync,
) -> None:
    from app.modules.data_firewall.firewall import FirewallOutcome
    from unittest.mock import MagicMock

    now = datetime(2026, 6, 17, 12, 0, 0, tzinfo=timezone.utc)
    expected_cutoff = now - timedelta(days=60)
    mock_authorize.return_value = FirewallOutcome(
        passed=True,
        reject_reason=None,
        failed_rules=[],
        forced_log_status=None,
        page_role_verdict=None,
        notes={},
        signed_record=MagicMock(),
    )
    mock_write_sync.return_value = MagicMock(ok=True, rows_affected=0)

    session = MagicMock()
    mock_cm = MagicMock()
    mock_cm.__enter__.return_value = session
    mock_cm.__exit__.return_value = False
    mock_session_factory.return_value = mock_cm

    retention_delete_table("api_logs", now=now)

    fields = mock_authorize.call_args.kwargs["fields"]
    assert fields["cutoff_column"] == "created_at"
    assert fields["cutoff"] == expected_cutoff.isoformat()


def test_retention_cutoff_matches_registry_windows() -> None:
    now = datetime(2026, 6, 17, tzinfo=timezone.utc)
    for table, config in RETENTION_TABLES.items():
        cutoff = retention_cutoff(table=table, now=now)
        assert cutoff == now - timedelta(days=config.window_days)
