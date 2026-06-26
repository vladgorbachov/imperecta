"""Pure-logic tests for maintenance audit marks (DDL/COMMANDS DA-1)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.modules.data_firewall.firewall import evaluate_logs
from app.modules.data_firewall.signing import reset_signing_settings_cache, sign_batch, verify_batch
from app.modules.persist.logs_write import build_api_log_fields
from app.modules.persist.maintenance_audit import record_maintenance_audit


@pytest.fixture(autouse=True)
def _data_firewall_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATA_FIREWALL_SIGNING_SECRET", "unit-test-data-firewall-secret")
    reset_signing_settings_cache()
    yield
    reset_signing_settings_cache()


def test_record_maintenance_audit_builds_valid_api_log_fields() -> None:
    with patch("app.modules.persist.maintenance_audit.write_logs_sync") as mock_write:
        mock_write.return_value = MagicMock(ok=True, inserted_count=1, rejected_count=0)
        record_maintenance_audit(
            op="REFRESH MV",
            target="mv_daily_price_summary",
            status="success",
            duration_ms=120,
        )

    mock_write.assert_called_once()
    rows = mock_write.call_args.kwargs["rows"]
    assert len(rows) == 1
    row = rows[0]
    assert row["service"] == "maintenance"
    assert row["endpoint"] == "REFRESH MV:mv_daily_price_summary"
    assert row["method"] == "REFRESH"
    assert len(row["method"]) <= 10
    assert row["status"] == "success"
    assert row["duration_ms"] == 120

    outcome = evaluate_logs(rows, table="api_logs", db=MagicMock(), reject_source="test")
    assert outcome.passed is True
    assert outcome.signed_batch is not None


def test_maintenance_audit_swallows_write_failure() -> None:
    with patch(
        "app.modules.persist.maintenance_audit.write_logs_sync",
        side_effect=RuntimeError("audit boom"),
    ):
        record_maintenance_audit(
            op="CREATE PARTITION",
            target="fact_price_202607",
            status="error",
            detail="disk full",
        )


def test_maintenance_mark_signature_binds_row() -> None:
    row = build_api_log_fields(
        service="maintenance",
        endpoint="RETENTION DELETE:multi_table",
        method="DELETE",
        status="success",
        error_message="scrape_logs=10 api_logs=2",
    )
    signature = sign_batch(table="api_logs", operation="insert", rows=[row], locator={})
    assert signature is not None
    assert verify_batch(
        table="api_logs",
        operation="insert",
        rows=[row],
        locator={},
        signature=signature,
    )
    tampered = dict(row)
    tampered["error_message"] = "tampered"
    assert not verify_batch(
        table="api_logs",
        operation="insert",
        rows=[tampered],
        locator={},
        signature=signature,
    )


def test_maintenance_audit_accepts_user_id() -> None:
    user_id = uuid4()
    with patch("app.modules.persist.maintenance_audit.write_logs_sync") as mock_write:
        mock_write.return_value = MagicMock(ok=True)
        record_maintenance_audit(
            op="CHECK REPAIR",
            target="scrape_jobs.job_type",
            status="success",
            user_id=user_id,
        )
    row = mock_write.call_args.kwargs["rows"][0]
    assert row["user_id"] == str(user_id)
    assert row["method"] == "ALTER"
