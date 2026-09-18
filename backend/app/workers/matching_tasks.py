"""Product matching beat task (roadmap item 3 slice M1).

Sync sessions only (engine helpers open short-lived sync sessions
internally) — no async bridge needed. Idempotent by construction:
group ids are deterministic uuid5 values and every processed row gets a
match_method, so a redelivered tick only picks up what a dead run missed.
"""

from __future__ import annotations

import structlog

from app.modules.matching.engine import MATCH_BATCH_SIZE, run_match_tick
from app.observability.sentry_init import capture_exception_if_initialized
from app.workers.celery_app import celery_app

slog = structlog.get_logger(__name__)


@celery_app.task(name="product_match_tick", bind=True, acks_late=True)
def product_match_tick(self, batch_size: int = MATCH_BATCH_SIZE) -> dict:
    """Drain one batch of unprocessed products into match groups."""
    try:
        return run_match_tick(batch_size)
    except Exception as exc:
        slog.error("product_match_tick_failed", error=str(exc)[:500])
        capture_exception_if_initialized(exc)
        return {"status": f"error:{type(exc).__name__}"}
