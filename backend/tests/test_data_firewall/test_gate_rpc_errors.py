"""Unit tests for gate RPC error mapping and service_alert carve-out (no DB)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.modules.data_firewall.signing import SignedRecord, reset_signing_settings_cache, sign
from app.modules.data_firewall.contracts import extract_locator
from app.modules.persist.gate_rpc import GateRpcError, _classify_gate_error
from app.modules.persist.writer import (
    PersistContext,
    build_dim_product_fields,
    write_sync,
)


@pytest.fixture(autouse=True)
def _data_firewall_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATA_FIREWALL_SIGNING_SECRET", "unit-test-data-firewall-secret")
    reset_signing_settings_cache()
    yield
    reset_signing_settings_cache()


def _signed(table: str, operation: str, fields: dict) -> SignedRecord:
    locator = extract_locator(table, fields)
    signature = sign(table=table, operation=operation, fields=fields, locator=locator)
    assert signature is not None
    return SignedRecord(
        table=table,
        operation=operation,
        locator=locator,
        fields=fields,
        signature=signature,
    )


def test_classify_gate_error_kinds() -> None:
    assert _classify_gate_error("invalid_signature") == "invalid_signature"
    assert _classify_gate_error("ERROR: signing_unavailable") == "signing_unavailable"
    assert _classify_gate_error("unsupported_operation") == "rpc_error"


@patch("app.modules.persist.writer.slog")
@patch("app.modules.persist.writer.write_service_alert_isolated")
@patch("app.modules.persist.writer.write_reject_data")
@patch("app.modules.persist.writer.exec_write_record")
def test_invalid_signature_records_reject_and_alert(
    mock_exec: MagicMock,
    mock_reject: MagicMock,
    mock_alert: MagicMock,
    mock_slog: MagicMock,
) -> None:
    mock_exec.side_effect = GateRpcError("invalid_signature", "invalid_signature")
    product_id = uuid4()
    fields = build_dim_product_fields(
        product_id=product_id,
        name="Item",
        name_normalized="item",
    )
    signed = _signed("dim_product", "insert", fields)
    db = MagicMock()

    result = write_sync(db, signed, ctx=PersistContext(source="test"))

    assert result.ok is False
    mock_reject.assert_called_once()
    assert mock_reject.call_args.kwargs["reject_reason"] == "gate_write_invalid_signature"
    mock_alert.assert_called_once()
    assert mock_alert.call_args.kwargs["anomaly_type"] == "gate_write_invalid_signature"
    assert mock_alert.call_args.kwargs["severity"] == "warning"
    mock_slog.warning.assert_called_once()


@patch("app.modules.persist.writer.slog")
@patch("app.modules.persist.writer.write_service_alert_isolated")
@patch("app.modules.persist.writer.write_reject_data")
@patch("app.modules.persist.writer.exec_write_record")
def test_signing_unavailable_raises_after_alert(
    mock_exec: MagicMock,
    mock_reject: MagicMock,
    mock_alert: MagicMock,
    mock_slog: MagicMock,
) -> None:
    mock_exec.side_effect = GateRpcError("signing_unavailable", "signing_unavailable")
    product_id = uuid4()
    fields = build_dim_product_fields(
        product_id=product_id,
        name="Item",
        name_normalized="item",
    )
    signed = _signed("dim_product", "insert", fields)
    db = MagicMock()

    with pytest.raises(GateRpcError) as exc_info:
        write_sync(db, signed, ctx=PersistContext(source="test"))

    assert exc_info.value.kind == "signing_unavailable"
    mock_reject.assert_not_called()
    mock_alert.assert_called_once()
    assert mock_alert.call_args.kwargs["anomaly_type"] == "gate_write_signing_unavailable"
    assert mock_alert.call_args.kwargs["severity"] == "critical"
    mock_slog.error.assert_called_once()


@patch("app.modules.persist.writer.slog")
@patch("app.modules.persist.writer.write_service_alert_isolated")
@patch("app.modules.persist.writer.write_reject_data")
@patch("app.modules.persist.writer.exec_write_record")
def test_rpc_error_raises_after_alert(
    mock_exec: MagicMock,
    mock_reject: MagicMock,
    mock_alert: MagicMock,
    mock_slog: MagicMock,
) -> None:
    mock_exec.side_effect = GateRpcError("rpc_error", "unsupported_operation")
    product_id = uuid4()
    fields = build_dim_product_fields(
        product_id=product_id,
        name="Item",
        name_normalized="item",
    )
    signed = _signed("dim_product", "insert", fields)
    db = MagicMock()

    with pytest.raises(GateRpcError) as exc_info:
        write_sync(db, signed, ctx=PersistContext(source="test"))

    assert exc_info.value.kind == "rpc_error"
    mock_reject.assert_not_called()
    mock_alert.assert_called_once()
    assert mock_alert.call_args.kwargs["anomaly_type"] == "gate_write_rpc_error"
    mock_slog.error.assert_called_once()


@patch("app.modules.data_firewall.service_alert_store.slog")
def test_write_service_alert_isolated_never_raises(
    mock_slog: MagicMock,
) -> None:
    from app.modules.data_firewall.service_alert_store import write_service_alert_isolated

    mock_db = MagicMock()
    mock_db.add.side_effect = RuntimeError("db down")

    with patch("app.database.sync_session_factory", return_value=mock_db):
        write_service_alert_isolated(
            module="data_firewall",
            submodule="persist_rpc",
            severity="error",
            anomaly_type="gate_write_rpc_error",
            message="test",
        )

    mock_slog.error.assert_called_once()
    mock_db.close.assert_called_once()
