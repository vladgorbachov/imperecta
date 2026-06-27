"""Discovery operational service alerts (artefact-2 gate-routed, fail-open)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import structlog

from app.modules.persist.service_alerts_write import (
    build_service_alert_fields,
    write_service_alert_async,
)

slog = structlog.get_logger(__name__)

_VALID_SEVERITIES = frozenset({"info", "warning", "error", "critical"})


def _merge_context(
    *,
    marketplace_id: UUID | None,
    context: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Build JSON-serialisable alert context; inject marketplace_id when provided."""
    if marketplace_id is None and not context:
        return None
    merged: dict[str, Any] = dict(context) if context else {}
    if marketplace_id is not None:
        merged["marketplace_id"] = str(marketplace_id)
    return merged


def _log_emit(
    severity: str,
    event_name: str,
    *,
    submodule: str,
    anomaly_type: str,
    alert_context: dict[str, Any] | None,
    persisted: bool | None = None,
) -> None:
    """Emit structlog for a service alert attempt (success path)."""
    log_kwargs: dict[str, Any] = {
        "submodule": submodule,
        "anomaly_type": anomaly_type,
        "severity": severity,
    }
    if alert_context is not None:
        log_kwargs["context"] = alert_context
    if persisted is not None:
        log_kwargs["persisted"] = persisted
    if severity == "info":
        slog.info(event_name, **log_kwargs)
    elif severity == "warning":
        slog.warning(event_name, **log_kwargs)
    else:
        slog.error(event_name, **log_kwargs)


async def emit_discovery_service_alert(
    submodule: str,
    severity: str,
    anomaly_type: str,
    message: str,
    *,
    marketplace_id: UUID | None = None,
    context: dict[str, Any] | None = None,
) -> None:
    """Emit one discovery service alert through the META gate.

    Does not decide *when* to alert — callers own detection logic.

    Fail-open: never raises. On gate/write failure, logs and returns so
    discovery continues.

    Callers must not put secrets in ``message`` or ``context`` (no tokens,
    credentials, or full URLs with query strings — host only if a URL is needed).
    """
    if severity not in _VALID_SEVERITIES:
        slog.warning(
            "discovery_service_alert_invalid_severity",
            submodule=submodule,
            anomaly_type=anomaly_type,
            severity=severity,
        )
        return

    alert_context = _merge_context(marketplace_id=marketplace_id, context=context)
    event_name = f"discovery_{anomaly_type}"

    try:
        fields = build_service_alert_fields(
            module="discovery",
            submodule=submodule,
            severity=severity,
            anomaly_type=anomaly_type,
            message=message,
            context=alert_context,
        )
        result = await write_service_alert_async(
            fields=fields,
            reject_source="discovery",
        )
        _log_emit(
            severity,
            event_name,
            submodule=submodule,
            anomaly_type=anomaly_type,
            alert_context=alert_context,
            persisted=bool(result.ok),
        )
        if not result.ok:
            slog.warning(
                "discovery_service_alert_emit_rejected",
                submodule=submodule,
                anomaly_type=anomaly_type,
            )
    except Exception as exc:
        slog.warning(
            "discovery_service_alert_emit_failed",
            submodule=submodule,
            anomaly_type=anomaly_type,
            exc_type=type(exc).__name__,
        )
