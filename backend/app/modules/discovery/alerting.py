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


FETCH_EMPTY_SOUP_MIN_SAMPLES = 5
FETCH_EMPTY_SOUP_RATE_THRESHOLD = 0.8


async def emit_fetch_empty_soup_spike_if_needed(
    *,
    marketplace_id: UUID,
    phase: str,
    total_fetches: int,
    empty_fetches: int,
    requires_js: bool,
    scrape_tier: int,
) -> None:
    """Emit when a phase sees a high empty-soup fetch rate (local counters)."""
    if total_fetches < FETCH_EMPTY_SOUP_MIN_SAMPLES:
        return
    empty_rate = empty_fetches / total_fetches
    if empty_rate < FETCH_EMPTY_SOUP_RATE_THRESHOLD:
        return
    await emit_discovery_service_alert(
        "fetch_adapter",
        "warning",
        "fetch_empty_soup_spike",
        (
            f"Fetch empty soup spike marketplace_id={marketplace_id} "
            f"phase={phase}"
        ),
        marketplace_id=marketplace_id,
        context={
            "phase": phase,
            "total_fetches": total_fetches,
            "empty_fetches": empty_fetches,
            "empty_rate": empty_rate,
            "requires_js": requires_js,
            "scrape_tier": scrape_tier,
        },
    )


CANONICAL_MISSING_MIN_CLASSIFIED = 10
CANONICAL_MISSING_RATE_THRESHOLD = 0.9


async def emit_canonical_missing_rate_high_if_needed(
    *,
    marketplace_id: UUID,
    classified: int,
    canonical_missing: int,
) -> None:
    """Emit when most soup-classified pages lack a canonical link."""
    if classified < CANONICAL_MISSING_MIN_CLASSIFIED:
        return
    rate = canonical_missing / classified
    if rate < CANONICAL_MISSING_RATE_THRESHOLD:
        return
    await emit_discovery_service_alert(
        "url_canonicalizer",
        "info",
        "canonical_missing_rate_high",
        (
            f"Canonical missing rate high marketplace_id={marketplace_id} "
            f"rate={rate:.2f}"
        ),
        marketplace_id=marketplace_id,
        context={
            "classified": classified,
            "canonical_missing": canonical_missing,
            "rate": rate,
        },
    )


CLASSIFY_UNKNOWN_MIN_CLASSIFIED = 10
CLASSIFY_UNKNOWN_RATE_THRESHOLD = 0.7
CLASSIFY_UNKNOWN_ALERT_MODES = frozenset({"full", "full_large"})


async def emit_classify_unknown_rate_high_if_needed(
    *,
    marketplace_id: UUID,
    classified: int,
    unknown_count: int,
    mode: str,
) -> None:
    """Emit when most soup-classified pages return structural role unknown."""
    if mode not in CLASSIFY_UNKNOWN_ALERT_MODES:
        return
    if classified < CLASSIFY_UNKNOWN_MIN_CLASSIFIED:
        return
    rate = unknown_count / classified
    if rate < CLASSIFY_UNKNOWN_RATE_THRESHOLD:
        return
    await emit_discovery_service_alert(
        "classifier_adapter",
        "warning",
        "classify_unknown_rate_high",
        (
            f"Classify unknown rate high marketplace_id={marketplace_id} "
            f"mode={mode} rate={rate:.2f}"
        ),
        marketplace_id=marketplace_id,
        context={
            "classified": classified,
            "unknown_count": unknown_count,
            "rate": rate,
            "mode": mode,
        },
    )
