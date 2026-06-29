"""Sanctioned diagnostic carve-out for service_alerts INSERT.

WHAT
----
service_alerts records operational anomalies (gate failures, signing outages, …).
Rows are class-designated ``alert_class='service'`` and are not HMAC-signed.

WHY THIS BYPASSES THE GATE
--------------------------
Gate-failure alerts must be recordable when the gate or signing vault is broken —
the same guarantee boundary as reject_data. Unsigned by design.

GUARANTEE BOUNDARY
------------------
- INSERT: unsigned carve-out; ``write_service_alert_isolated`` only for isolated
  gate-failure paths. Must never raise (last resort: structlog.error).
- Never put secrets or field values in message/context.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import structlog

from app.models.app_tables import ServiceAlert

slog = structlog.get_logger(__name__)

SANCTIONED_SERVICE_ALERT_INSERT_FUNCTIONS = ("write_service_alert_isolated",)


def write_service_alert_isolated(
    *,
    module: str,
    submodule: str,
    severity: str,
    anomaly_type: str,
    message: str,
    context: dict[str, Any] | None = None,
    alert_class: str = "service",
) -> None:
    """Direct INSERT on an independent session; must not raise."""
    from app.database import sync_session_factory

    db = sync_session_factory()
    try:
        db.add(
            ServiceAlert(
                id=uuid4(),
                alert_class=alert_class,
                module=module,
                submodule=submodule,
                severity=severity,
                anomaly_type=anomaly_type,
                message=message,
                context=context,
            ),
        )
        db.commit()
    except Exception:
        slog.error(
            "service_alert_isolated_write_failed",
            module=module,
            submodule=submodule,
            anomaly_type=anomaly_type,
            severity=severity,
        )
    finally:
        db.close()
