"""Redis-backed relay of celery worker log lines for admin live monitor."""

from __future__ import annotations

import json
import logging
import threading
import time
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any, Iterator
from uuid import UUID

from app.config import Settings

REDIS_LOG_KEY = "pipeline:worker_deploy_log"
REDIS_LOG_MAX_LINES = 500
RELAY_LOGGER_NAMES = (
    "app.modules.scraper",
    "celery",
    "celery.task",
    "celery.worker",
)

# Per-instance handler emit throttle. Drops intra-window structlog lines so a
# 25k-fetch scrape can't flood Upstash. Lossy by design (the live monitor only
# needs heartbeat-grade granularity); the worker_log_tail in metadata + the
# full structlog stream in Railway remain complete.
HANDLER_MIN_EMIT_INTERVAL_S = 0.5

_active_job_id: UUID | None = None
_redis_client: Any | None = None

# Per-parent ref-counted handler registry. Two children of the SAME parent in
# one worker process share ONE handler so each captured log line is pushed
# exactly once (avoids the double-emit you'd get if both children attached
# their own per-instance handler to the same module loggers). Children of
# DIFFERENT parents get DIFFERENT handlers (correct isolation). The registry
# value is (handler, attach_count); the CM increments on entry, decrements on
# exit, and detaches+evicts when the count hits zero.
_handler_registry: dict[UUID, tuple["PipelineWorkerLogHandler", int]] = {}
_handler_registry_lock = threading.Lock()


def set_active_pipeline_job(job_id: UUID | None) -> None:
    """Bind relay lines to a parent pipeline job while the Celery task runs."""
    global _active_job_id
    _active_job_id = job_id


def get_active_pipeline_job() -> UUID | None:
    return _active_job_id


def _get_redis() -> Any:
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    import redis

    settings = Settings()
    _redis_client = redis.from_url(settings.redis_url, decode_responses=True)
    return _redis_client


def _format_relay_line(line: str) -> str:
    text = " ".join(str(line or "").split())
    if len(text) > 480:
        return text[:477] + "..."
    return text


def push_relay_line(line: str, *, job_id: UUID | None = None) -> int:
    """Append one log line to the shared worker relay buffer."""
    text = _format_relay_line(line)
    if not text:
        return 0
    bound_job = job_id or _active_job_id
    client = _get_redis()
    seq = int(client.incr(f"{REDIS_LOG_KEY}:seq"))
    payload = json.dumps(
        {
            "seq": seq,
            "at": datetime.now(UTC).isoformat(),
            "line": text,
            "job_id": str(bound_job) if bound_job else None,
        },
        separators=(",", ":"),
    )
    client.rpush(REDIS_LOG_KEY, payload)
    client.ltrim(REDIS_LOG_KEY, -REDIS_LOG_MAX_LINES, -1)
    return seq


def fetch_relay_lines(*, after: int = 0, limit: int = 50) -> dict[str, Any]:
    """Return relay lines with seq > after (newest batch up to limit)."""
    client = _get_redis()
    raw_items = client.lrange(REDIS_LOG_KEY, 0, -1)
    parsed: list[dict[str, Any]] = []
    for raw in raw_items:
        try:
            item = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if not isinstance(item, dict):
            continue
        seq = int(item.get("seq") or 0)
        if seq <= after:
            continue
        line = str(item.get("line") or "").strip()
        if not line:
            continue
        parsed.append(
            {
                "seq": seq,
                "at": item.get("at"),
                "line": line,
                "job_id": item.get("job_id"),
            }
        )
    parsed.sort(key=lambda row: int(row["seq"]))
    if limit > 0:
        parsed = parsed[-limit:]
    next_cursor = int(parsed[-1]["seq"]) if parsed else after
    return {
        "lines": parsed,
        "next_cursor": next_cursor,
        "total_buffered": len(raw_items),
    }


class PipelineWorkerLogHandler(logging.Handler):
    """Capture scraper/celery log records into the Redis relay during pipeline runs.

    Concurrency-safe by construction: each instance carries its OWN ``job_id``
    so emitted records are stamped explicitly (does NOT rely on the racy
    ``_active_job_id`` module global). Per-instance throttling caps emit rate
    so a 25k-fetch scrape phase can't flood Redis/Upstash.
    """

    def __init__(
        self,
        job_id: UUID | None = None,
        *,
        min_interval_s: float = HANDLER_MIN_EMIT_INTERVAL_S,
    ) -> None:
        super().__init__()
        self._job_id = job_id
        self._min_interval_s = float(min_interval_s)
        self._last_emit_monotonic = 0.0

    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = record.getMessage()
            if not message:
                return
            now = time.monotonic()
            if now - self._last_emit_monotonic < self._min_interval_s:
                return
            self._last_emit_monotonic = now
            line = self.format(record)
            push_relay_line(line, job_id=self._job_id)
        except Exception:
            self.handleError(record)


def _attach_handler_for(job_id: UUID) -> "PipelineWorkerLogHandler":
    """Return the shared handler for ``job_id``, creating + attaching on first use.

    Concurrent ticks/children of the SAME parent share ONE handler instance
    via the ref-counted registry (so each captured record emits exactly one
    relay push, not one per attached handler). Different parents get
    independent handlers.
    """
    with _handler_registry_lock:
        existing = _handler_registry.get(job_id)
        if existing is not None:
            handler, count = existing
            _handler_registry[job_id] = (handler, count + 1)
            return handler
        handler = PipelineWorkerLogHandler(job_id=job_id)
        handler.setLevel(logging.INFO)
        handler.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s | %(levelname)s | %(message)s",
                datefmt="%H:%M:%S",
            )
        )
        for name in RELAY_LOGGER_NAMES:
            logging.getLogger(name).addHandler(handler)
        _handler_registry[job_id] = (handler, 1)
        return handler


def _detach_handler_for(job_id: UUID) -> None:
    """Decrement the ref count; on the last release detach + evict the handler."""
    with _handler_registry_lock:
        existing = _handler_registry.get(job_id)
        if existing is None:
            return
        handler, count = existing
        if count > 1:
            _handler_registry[job_id] = (handler, count - 1)
            return
        for name in RELAY_LOGGER_NAMES:
            logging.getLogger(name).removeHandler(handler)
        _handler_registry.pop(job_id, None)


@contextmanager
def pipeline_worker_log_relay(job_id: UUID) -> Iterator[None]:
    """Attach relay handler for the duration of a pipeline Celery task.

    The handler is per-instance (its own ``job_id`` + throttle) and shared
    across concurrent ticks/children of the same parent via a ref-counted
    registry. ``set_active_pipeline_job`` is still called for backward-compat
    with any reader that consults ``get_active_pipeline_job``, but the
    handler's stamping no longer depends on that global.
    """
    set_active_pipeline_job(job_id)
    _attach_handler_for(job_id)
    # Relay observability must NEVER crash the task body. Redis being
    # unreachable (transient outage, dev/test env without a broker) is fine —
    # we log and continue. The handler's own emit() is already broad-except'd.
    try:
        push_relay_line(f"pipeline job {job_id} started", job_id=job_id)
    except Exception:
        logging.getLogger(__name__).exception(
            "pipeline_worker_log_relay_start_push_failed job_id=%s", job_id
        )
    try:
        yield
    finally:
        try:
            push_relay_line(f"pipeline job {job_id} finished", job_id=job_id)
        except Exception:
            logging.getLogger(__name__).exception(
                "pipeline_worker_log_relay_finish_push_failed job_id=%s",
                job_id,
            )
        _detach_handler_for(job_id)
        set_active_pipeline_job(None)


_last_db_pulse: dict[str, float] = {}
DB_PULSE_MIN_SECONDS = 15.0


def should_pulse_db(job_id: UUID, *, force: bool = False) -> bool:
    if force:
        return True
    key = str(job_id)
    now = time.time()
    last = _last_db_pulse.get(key, 0.0)
    if now - last < DB_PULSE_MIN_SECONDS:
        return False
    _last_db_pulse[key] = now
    return True
