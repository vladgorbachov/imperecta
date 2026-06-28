"""Retention registry constants — service-data whitelist only."""

from __future__ import annotations

from typing import Final, NamedTuple


class RetentionTableConfig(NamedTuple):
    """Per-table retention window and cutoff column for bulk DELETE."""

    cutoff_column: str
    window_days: int


# Service-data whitelist only. User-data (ai_chat_messages) and analytic/client-data
# (alert_events) are physically excluded per invariant #11.
RETENTION_TABLES: Final[dict[str, RetentionTableConfig]] = {
    "service_alerts": RetentionTableConfig("triggered_at", 3),
    "reject_data": RetentionTableConfig("created_at", 3),
    "scrape_logs": RetentionTableConfig("created_at", 14),
    "api_logs": RetentionTableConfig("created_at", 60),
}

# Legacy alias: default window for the original service_alerts/reject_data pair.
RETENTION_DAYS: Final[int] = 3
