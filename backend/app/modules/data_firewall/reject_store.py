"""Resilient reject_data writes and spike alerting."""

from __future__ import annotations

import logging
import threading
import time
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy.orm import Session

from app.config import Settings
from app.models.reject_data import RejectData
from app.observability.sentry_init import capture_exception_if_initialized

logger = logging.getLogger(__name__)
slog = structlog.get_logger(__name__)

_lock = threading.Lock()
_recent_reject_timestamps: list[float] = []


def _spike_threshold() -> int:
    return Settings().data_firewall_reject_spike_threshold


def _prune_old_rejects(now: float, window_seconds: float = 60.0) -> None:
    global _recent_reject_timestamps
    cutoff = now - window_seconds
    _recent_reject_timestamps = [ts for ts in _recent_reject_timestamps if ts >= cutoff]


def reset_reject_spike_state() -> None:
    """Clear in-process spike counters (tests only)."""
    global _recent_reject_timestamps
    with _lock:
        _recent_reject_timestamps = []


def record_reject_spike_signal(
    *,
    source: str,
    reject_reason: str,
    rejected_by: str,
) -> None:
    """Emit structured warn; escalate to Sentry on burst threshold."""
    slog.warning(
        "data_firewall_reject",
        source=source,
        reject_reason=reject_reason,
        rejected_by=rejected_by,
    )
    now = time.monotonic()
    with _lock:
        _prune_old_rejects(now)
        _recent_reject_timestamps.append(now)
        count = len(_recent_reject_timestamps)
        threshold = _spike_threshold()
    if count >= threshold:
        try:
            import sentry_sdk

            if sentry_sdk.is_initialized():
                sentry_sdk.capture_message(
                    "data_firewall_reject_spike",
                    level="warning",
                    extras={
                        "count": count,
                        "threshold": threshold,
                        "source": source,
                        "reject_reason": reject_reason,
                        "rejected_by": rejected_by,
                    },
                )
        except Exception as exc:
            capture_exception_if_initialized(exc)


def write_reject_data(
    db: Session,
    *,
    source: str,
    table_target: str,
    reject_reason: str,
    raw_payload: dict[str, Any],
    rejected_by: str,
    failed_rules: list[str] | None = None,
    marketplace_id: UUID | None = None,
    listing_id: UUID | None = None,
    signature_present: bool = False,
    operation: str = "insert",
) -> None:
    """Insert reject_data row; failures are logged and never crash the pipeline."""
    record_reject_spike_signal(
        source=source,
        reject_reason=reject_reason,
        rejected_by=rejected_by,
    )
    try:
        db.add(
            RejectData(
                source=source,
                table_target=table_target,
                operation=operation,
                marketplace_id=marketplace_id,
                listing_id=listing_id,
                reject_reason=reject_reason,
                failed_rules=failed_rules,
                raw_payload=raw_payload,
                signature_present=signature_present,
                rejected_by=rejected_by,
            ),
        )
        db.flush()
    except Exception:
        logger.exception(
            "reject_data_write_failed source=%s table=%s reason=%s",
            source,
            table_target,
            reject_reason,
        )
