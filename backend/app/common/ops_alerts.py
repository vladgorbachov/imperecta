"""Generic operational service-alert emitter for non-discovery modules.

Mirrors ``app.modules.discovery.alerting`` but is module-agnostic: scraper,
parser, quality and market_data emit through here (module='discovery' keeps
its own richer emitter). Writes go through the META gate
(``write_service_alert_sync``), fail-open, and are rate-limited in-process so
a hot failure loop cannot flood service_alerts: at most one alert per
(module, submodule, anomaly_type, entity) per ``RATE_LIMIT_SECONDS``.

Callers must not put secrets in ``message`` or ``context``.
"""

from __future__ import annotations

import time
from typing import Any

import structlog

from app.modules.persist.service_alerts_write import (
    build_service_alert_fields,
    write_service_alert_sync,
)

slog = structlog.get_logger(__name__)

_VALID_SEVERITIES = frozenset({"info", "warning", "error", "critical"})

RATE_LIMIT_SECONDS = 300.0
_last_emit: dict[tuple[str, str, str, str], float] = {}


def _rate_limited(key: tuple[str, str, str, str]) -> bool:
    now = time.monotonic()
    last = _last_emit.get(key)
    if last is not None and now - last < RATE_LIMIT_SECONDS:
        return True
    _last_emit[key] = now
    if len(_last_emit) > 4096:  # unbounded-growth guard
        cutoff = now - RATE_LIMIT_SECONDS
        for stale_key in [k for k, ts in _last_emit.items() if ts < cutoff]:
            del _last_emit[stale_key]
    return False


def emit_ops_alert(
    *,
    module: str,
    submodule: str,
    severity: str,
    anomaly_type: str,
    message: str,
    entity: str = "",
    context: dict[str, Any] | None = None,
) -> bool:
    """Emit one gate-routed service alert; returns True when persisted.

    ``entity`` scopes the rate limit (marketplace id, listing id, host…):
    the same anomaly for different entities alerts independently.
    Fail-open: never raises.
    """
    if severity not in _VALID_SEVERITIES:
        slog.warning(
            "ops_alert_invalid_severity",
            module=module,
            anomaly_type=anomaly_type,
            severity=severity,
        )
        return False
    if _rate_limited((module, submodule, anomaly_type, entity)):
        return False

    try:
        fields = build_service_alert_fields(
            module=module,
            submodule=submodule,
            severity=severity,
            anomaly_type=anomaly_type,
            message=message,
            context=context,
        )
        result = write_service_alert_sync(fields=fields, reject_source=module)
        log = slog.info if severity == "info" else slog.warning
        log(
            f"{module}_{anomaly_type}",
            submodule=submodule,
            severity=severity,
            persisted=bool(result.ok),
            context=context,
        )
        return bool(result.ok)
    except Exception as exc:
        slog.warning(
            "ops_alert_emit_failed",
            module=module,
            anomaly_type=anomaly_type,
            exc_type=type(exc).__name__,
        )
        return False
