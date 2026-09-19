"""Maintenance tasks: service-data retention (DDL moved to pg_cron)."""

from __future__ import annotations

import structlog

from app.modules.persist.retention import run_retention_pass
from app.observability.sentry_init import capture_exception_if_initialized
from app.workers.celery_app import celery_app

slog = structlog.get_logger(__name__)


@celery_app.task(name="run_service_data_retention")
def run_service_data_retention() -> dict[str, int]:
    """Delete service-data rows via the gate (per-table windows, fail-open)."""
    try:
        return run_retention_pass()
    except Exception as exc:
        slog.error("retention_pass_failed", error=str(exc)[:500])
        capture_exception_if_initialized(exc)
        return {}


def purge_marketplace_state_sync(marketplace_codes: list[str]) -> dict[str, int]:
    """Drop every Redis key a marketplace left behind (harvest cursor and
    list-mode probe, rotation membership, enumeration run stashes, parked
    budget retries). The DB side is `maintenance.purge_marketplace`; this is
    its Redis twin, called by the RU/BY/KZ purge (legal clean-up WP1) and by
    the opt-out / delete path (WP5). Page-cache entries are keyed by URL hash
    and expire on their own (PAGE_CACHE_TTL_SEC)."""
    from app.modules.scraper.pipeline.worker_log_relay import _get_redis
    from app.workers.harvest_tasks import (
        HARVEST_CURSOR_KEY,
        HARVEST_LIST_MODE_KEY,
        HARVEST_ROTATION_KEY,
    )
    from app.workers.onboarding_tasks import BUDGET_RETRY_KEY

    client = _get_redis()
    removed = {"keys": 0, "rotation": 0, "budget_retry": 0}
    for code in marketplace_codes:
        removed["keys"] += int(
            client.delete(f"{HARVEST_CURSOR_KEY}{code}", f"{HARVEST_LIST_MODE_KEY}{code}")
        )
        removed["rotation"] += int(client.zrem(HARVEST_ROTATION_KEY, code))
        run_keys = list(client.scan_iter(match=f"enumrun:{code}:*", count=500))
        if run_keys:
            removed["keys"] += int(client.delete(*run_keys))
        for field in client.hkeys(BUDGET_RETRY_KEY) or []:
            name = field.decode() if isinstance(field, bytes) else str(field)
            if name.split(":")[1:2] == [code]:
                removed["budget_retry"] += int(client.hdel(BUDGET_RETRY_KEY, field))
    return removed


@celery_app.task(name="purge_marketplace_state")
def purge_marketplace_state(marketplace_codes: list[str]) -> dict[str, int]:
    """Redis clean-up for purged marketplaces (see purge_marketplace_state_sync)."""
    try:
        summary = purge_marketplace_state_sync(list(marketplace_codes))
        slog.info("purge_marketplace_state_done", codes=marketplace_codes, **summary)
        return summary
    except Exception as exc:
        slog.error("purge_marketplace_state_failed", error=str(exc)[:500])
        capture_exception_if_initialized(exc)
        return {}
