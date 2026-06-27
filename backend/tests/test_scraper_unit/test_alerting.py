"""DB-free tests for discovery service alert emitter."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.modules.discovery.alerting import emit_discovery_service_alert
from app.modules.persist.service_alerts_write import ServiceAlertWriteResult


@pytest.mark.asyncio
async def test_emit_discovery_service_alert_writes_gate_fields() -> None:
    mp_id = uuid4()
    with (
        patch(
            "app.modules.discovery.alerting.write_service_alert_async",
            new_callable=AsyncMock,
            return_value=ServiceAlertWriteResult(ok=True, rows_affected=1),
        ) as write_mock,
        patch("app.modules.discovery.alerting.slog") as slog_mock,
    ):
        await emit_discovery_service_alert(
            "budget_governor",
            "warning",
            "resume_index_desync",
            "divergence detected",
            marketplace_id=mp_id,
            context={"resume_index": 1, "categories_len": 1},
        )

    write_mock.assert_awaited_once()
    kwargs = write_mock.await_args.kwargs
    assert kwargs["reject_source"] == "discovery"
    fields = kwargs["fields"]
    assert fields["module"] == "discovery"
    assert fields["submodule"] == "budget_governor"
    assert fields["severity"] == "warning"
    assert fields["anomaly_type"] == "resume_index_desync"
    assert fields["message"] == "divergence detected"
    assert fields["context"]["marketplace_id"] == str(mp_id)
    assert fields["context"]["resume_index"] == 1
    slog_mock.warning.assert_called_once()
    assert (
        slog_mock.warning.call_args.args[0] == "discovery_resume_index_desync"
    )


@pytest.mark.asyncio
async def test_emit_discovery_service_alert_swallows_write_failure() -> None:
    with (
        patch(
            "app.modules.discovery.alerting.write_service_alert_async",
            new_callable=AsyncMock,
            side_effect=RuntimeError("gate down"),
        ),
        patch("app.modules.discovery.alerting.slog") as slog_mock,
    ):
        await emit_discovery_service_alert(
            "gate_persist",
            "error",
            "pool_batch_commit_failed",
            "batch commit failed",
        )

    slog_mock.warning.assert_called_once()
    assert (
        slog_mock.warning.call_args.args[0]
        == "discovery_service_alert_emit_failed"
    )
    assert slog_mock.warning.call_args.kwargs["exc_type"] == "RuntimeError"


@pytest.mark.asyncio
async def test_emit_discovery_service_alert_rejects_invalid_severity() -> None:
    with (
        patch(
            "app.modules.discovery.alerting.write_service_alert_async",
            new_callable=AsyncMock,
        ) as write_mock,
        patch("app.modules.discovery.alerting.slog") as slog_mock,
    ):
        await emit_discovery_service_alert(
            "cursor_store",
            "urgent",
            "frontier_deserialize_failed",
            "bad severity",
        )

    write_mock.assert_not_awaited()
    slog_mock.warning.assert_called_once()
    assert (
        slog_mock.warning.call_args.args[0]
        == "discovery_service_alert_invalid_severity"
    )
