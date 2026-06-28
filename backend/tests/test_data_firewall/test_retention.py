"""DB-free tests for service-data retention (gate DELETE + audit + alert)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.modules.data_firewall.firewall import FirewallOutcome
from app.modules.data_firewall.retention_gate import authorize_retention_delete
from app.modules.data_firewall.signing import SignedRecord, reset_signing_settings_cache, sign
from app.modules.persist.retention import (
    RetentionTableNotWhitelistedError,
    assert_retention_table_whitelisted,
    retention_cutoff,
    retention_delete_table,
    run_retention_pass,
)
from app.modules.persist.retention_config import (
    RETENTION_DAYS,
    RETENTION_TABLES,
    RetentionTableConfig,
)
from app.modules.persist.writer import (
    PersistContext,
    PersistResult,
    SUPPORTED_WRITE_OPERATIONS,
    write_sync,
)


@pytest.fixture(autouse=True)
def _data_firewall_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATA_FIREWALL_SIGNING_SECRET", "unit-test-data-firewall-secret")
    reset_signing_settings_cache()
    yield
    reset_signing_settings_cache()


def _fixed_now() -> datetime:
    return datetime(2026, 6, 17, 12, 0, 0, tzinfo=timezone.utc)


def test_retention_registry_and_per_table_windows() -> None:
    assert RETENTION_DAYS == 3
    assert RETENTION_TABLES == {
        "service_alerts": RetentionTableConfig("triggered_at", 3),
        "reject_data": RetentionTableConfig("created_at", 3),
        "scrape_logs": RetentionTableConfig("created_at", 14),
        "api_logs": RetentionTableConfig("created_at", 60),
    }
    assert "alerts" not in RETENTION_TABLES
    assert "alert_events" not in RETENTION_TABLES
    assert SUPPORTED_WRITE_OPERATIONS["scrape_logs"] == frozenset(
        {"insert", "retention_delete"},
    )
    assert SUPPORTED_WRITE_OPERATIONS["api_logs"] == frozenset(
        {"insert", "retention_delete"},
    )


def test_whitelist_guard_rejects_analytic_table() -> None:
    with pytest.raises(RetentionTableNotWhitelistedError, match="alerts"):
        assert_retention_table_whitelisted("alerts")


def test_retention_cutoff_uses_per_table_window() -> None:
    now = _fixed_now()
    assert retention_cutoff(table="service_alerts", now=now) == now - timedelta(days=3)
    assert retention_cutoff(table="scrape_logs", now=now) == now - timedelta(days=14)
    assert retention_cutoff(table="api_logs", now=now) == now - timedelta(days=60)


def test_per_table_cutoff_columns_in_gate_fields() -> None:
    now = _fixed_now()
    for table, config in RETENTION_TABLES.items():
        cutoff = retention_cutoff(table=table, now=now)
        fields = {
            "cutoff_column": config.cutoff_column,
            "cutoff": cutoff.isoformat(),
        }
        outcome = authorize_retention_delete(
            table=table,
            fields=fields,
            db=None,
            reject_source="test",
        )
        assert outcome.passed is True
        assert outcome.signed_record is not None
        assert outcome.signed_record.fields["cutoff_column"] == config.cutoff_column


def test_gate_rejects_wrong_cutoff_column_for_table() -> None:
    now = _fixed_now()
    fields = {
        "cutoff_column": "created_at",
        "cutoff": retention_cutoff(table="service_alerts", now=now).isoformat(),
    }
    outcome = authorize_retention_delete(
        table="service_alerts",
        fields=fields,
        db=None,
        reject_source="test",
    )
    assert outcome.passed is False
    assert outcome.reject_reason == "retention_cutoff_column_mismatch"


@patch("app.modules.persist.retention.write_sync")
@patch("app.modules.persist.retention.authorize_retention_delete")
@patch("app.modules.persist.retention.sync_session_factory")
def test_retention_delete_routes_through_gate_and_persist(
    mock_session_factory,
    mock_authorize,
    mock_write_sync,
) -> None:
    now = _fixed_now()
    cutoff = retention_cutoff(table="service_alerts", now=now)
    fields = {
        "cutoff_column": "triggered_at",
        "cutoff": cutoff.isoformat(),
    }
    signature = sign(
        table="service_alerts",
        operation="retention_delete",
        fields=fields,
        locator={},
    )
    assert signature is not None
    signed = SignedRecord(
        table="service_alerts",
        operation="retention_delete",
        locator={},
        fields=fields,
        signature=signature,
    )
    mock_authorize.return_value = FirewallOutcome(
        passed=True,
        reject_reason=None,
        failed_rules=[],
        forced_log_status=None,
        page_role_verdict=None,
        notes={},
        signed_record=signed,
    )
    mock_write_sync.return_value = PersistResult(ok=True, rows_affected=4)

    session = MagicMock()
    mock_cm = MagicMock()
    mock_cm.__enter__.return_value = session
    mock_cm.__exit__.return_value = False
    mock_session_factory.return_value = mock_cm

    result = retention_delete_table("service_alerts", now=now)

    assert result.ok is True
    assert result.rows_affected == 4
    mock_authorize.assert_called_once()
    authorize_kwargs = mock_authorize.call_args.kwargs
    assert authorize_kwargs["table"] == "service_alerts"
    assert authorize_kwargs["fields"]["cutoff_column"] == "triggered_at"
    assert authorize_kwargs["fields"]["cutoff"] == cutoff.isoformat()
    mock_write_sync.assert_called_once()
    write_args, write_kwargs = mock_write_sync.call_args
    assert write_args[0] is session
    assert write_args[1] is signed
    assert write_kwargs["ctx"].source == "maintenance_retention"
    session.commit.assert_called_once()


@patch("app.modules.persist.retention.write_service_alert_sync")
@patch("app.modules.persist.retention.sync_session_factory")
def test_non_whitelisted_table_never_calls_gate(
    mock_session_factory,
    mock_alert,
) -> None:
    with pytest.raises(RetentionTableNotWhitelistedError):
        retention_delete_table("alerts", now=_fixed_now())
    mock_session_factory.assert_not_called()
    mock_alert.assert_not_called()


@patch("app.modules.persist.retention.write_service_alert_sync")
@patch("app.modules.persist.retention.write_sync")
@patch("app.modules.persist.retention.authorize_retention_delete")
@patch("app.modules.persist.retention.sync_session_factory")
def test_gate_reject_on_whitelisted_table_emits_maintenance_alert(
    mock_session_factory,
    mock_authorize,
    mock_write_sync,
    mock_alert,
) -> None:
    mock_authorize.return_value = FirewallOutcome(
        passed=False,
        reject_reason="invalid_signature",
        failed_rules=["invalid_signature"],
        forced_log_status=None,
        page_role_verdict=None,
        notes={},
        signed_record=None,
    )
    session = MagicMock()
    mock_cm = MagicMock()
    mock_cm.__enter__.return_value = session
    mock_cm.__exit__.return_value = False
    mock_session_factory.return_value = mock_cm

    result = retention_delete_table("reject_data", now=_fixed_now())

    assert result.ok is False
    mock_write_sync.assert_not_called()
    mock_alert.assert_called_once()
    alert_fields = mock_alert.call_args.kwargs["fields"]
    assert alert_fields["module"] == "maintenance"
    assert alert_fields["submodule"] == "retention"
    assert alert_fields["anomaly_type"] == "retention_delete_rejected"


@patch("app.modules.persist.retention.record_maintenance_audit")
@patch("app.modules.persist.retention.retention_delete_table")
def test_run_retention_pass_audits_each_table(mock_delete_table, mock_audit) -> None:
    mock_delete_table.side_effect = [
        PersistResult(ok=True, rows_affected=2),
        PersistResult(ok=True, rows_affected=5),
        PersistResult(ok=True, rows_affected=1),
        PersistResult(ok=True, rows_affected=3),
    ]
    deleted = run_retention_pass(now=_fixed_now())
    assert deleted == {
        "service_alerts": 2,
        "reject_data": 5,
        "scrape_logs": 1,
        "api_logs": 3,
    }
    assert mock_delete_table.call_count == 4
    assert mock_audit.call_count == 4
    audit_targets = [call.kwargs["target"] for call in mock_audit.call_args_list]
    assert audit_targets == [
        "service_alerts",
        "reject_data",
        "scrape_logs",
        "api_logs",
    ]
    for call in mock_audit.call_args_list:
        assert call.kwargs["op"] == "RETENTION DELETE"
        assert call.kwargs["status"] == "success"


def test_write_sync_retention_delete_executes_cutoff_predicate() -> None:
    now = _fixed_now()
    cutoff = retention_cutoff(table="reject_data", now=now)
    fields = {
        "cutoff_column": "created_at",
        "cutoff": cutoff.isoformat(),
    }
    signature = sign(
        table="reject_data",
        operation="retention_delete",
        fields=fields,
        locator={},
    )
    assert signature is not None
    signed = SignedRecord(
        table="reject_data",
        operation="retention_delete",
        locator={},
        fields=fields,
        signature=signature,
    )
    session = MagicMock()
    execute_result = MagicMock()
    execute_result.rowcount = 7
    session.execute.return_value = execute_result

    result = write_sync(session, signed, ctx=PersistContext(source="test"))

    assert result.ok is True
    assert result.rows_affected == 7
    session.execute.assert_called_once()
    delete_stmt = session.execute.call_args.args[0]
    compiled = str(delete_stmt.compile(compile_kwargs={"literal_binds": True}))
    assert "reject_data" in compiled.lower()
    assert "created_at" in compiled.lower()
    assert cutoff.isoformat()[:19] in compiled or str(cutoff.date()) in compiled


@patch("app.modules.persist.retention.run_retention_pass")
def test_celery_retention_task_fail_open(mock_run) -> None:
    from app.workers.maintenance_tasks import run_service_data_retention

    mock_run.side_effect = RuntimeError("beat worker must survive")
    assert run_service_data_retention() == {}
