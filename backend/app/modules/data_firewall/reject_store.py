"""Sanctioned diagnostic carve-out for reject_data INSERT (sites #34-35).

WHAT
----
reject_data is the diagnostic store for payloads the data_firewall gate rejected.
Rows capture source, table_target, reject_reason, failed_rules, raw_payload, and
metadata about the *rejected payload* (not the reject row itself).

WHY THIS BYPASSES THE GATE
--------------------------
reject_data INSERT intentionally does NOT go through evaluate_*/write_sync/signing.
A record about a rejected or unsigned payload cannot meaningfully pass the same
contract/HMAC that rejected it (recursion). The diagnostic path must keep working
when the gate or contract itself is broken — that is its purpose.

GUARANTEE BOUNDARY
------------------
- INSERT: unsigned by design; append-only diagnostic; never read back into the
  data plane; never exported.
- DELETE: retention_delete IS gated (authorize_retention_delete → write_sync).
- SINGLE SANCTIONED INSERT PATH: write_reject_data / write_reject_data_isolated
  only. Any reject_data INSERT outside reject_store is a bug.

signature_present on each row documents whether the *rejected payload* carried an
HMAC, not whether the reject_data row itself is signed.
"""

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

# Named boundary marker: the only sanctioned reject_data INSERT entry points.
SANCTIONED_REJECT_DATA_INSERT_FUNCTIONS = (
    "write_reject_data",
    "write_reject_data_isolated",
)

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


def _reject_data_row(
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
) -> RejectData:
    return RejectData(
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
    )


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
    """Sanctioned carve-out INSERT on caller session (flush only); failures are logged."""
    record_reject_spike_signal(
        source=source,
        reject_reason=reject_reason,
        rejected_by=rejected_by,
    )
    try:
        db.add(
            _reject_data_row(
                source=source,
                table_target=table_target,
                reject_reason=reject_reason,
                raw_payload=raw_payload,
                rejected_by=rejected_by,
                failed_rules=failed_rules,
                marketplace_id=marketplace_id,
                listing_id=listing_id,
                signature_present=signature_present,
                operation=operation,
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


def write_reject_data_isolated(
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
    """Sanctioned carve-out INSERT on an independent session (commits outside caller txn)."""
    from app.database import sync_session_factory

    record_reject_spike_signal(
        source=source,
        reject_reason=reject_reason,
        rejected_by=rejected_by,
    )
    db = sync_session_factory()
    try:
        db.add(
            _reject_data_row(
                source=source,
                table_target=table_target,
                reject_reason=reject_reason,
                raw_payload=raw_payload,
                rejected_by=rejected_by,
                failed_rules=failed_rules,
                marketplace_id=marketplace_id,
                listing_id=listing_id,
                signature_present=signature_present,
                operation=operation,
            ),
        )
        db.commit()
    except Exception:
        logger.exception(
            "reject_data_isolated_write_failed source=%s table=%s reason=%s",
            source,
            table_target,
            reject_reason,
        )
    finally:
        db.close()
