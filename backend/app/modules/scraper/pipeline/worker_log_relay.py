"""Redis-backed relay of celery worker log lines for admin live monitor."""

from __future__ import annotations

import json
import logging
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

_active_job_id: UUID | None = None
_redis_client: Any | None = None


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
    """Capture scraper/celery log records into the Redis relay during pipeline runs."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = record.getMessage()
            if not message:
                return
            line = f"{self.format(record)}"
            push_relay_line(line)
        except Exception:
            self.handleError(record)


@contextmanager
def pipeline_worker_log_relay(job_id: UUID) -> Iterator[None]:
    """Attach relay handler for the duration of a pipeline Celery task."""
    set_active_pipeline_job(job_id)
    handler = PipelineWorkerLogHandler()
    handler.setLevel(logging.INFO)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s | %(levelname)s | %(message)s",
            datefmt="%H:%M:%S",
        )
    )
    attached: list[tuple[logging.Logger, logging.Handler]] = []
    for name in RELAY_LOGGER_NAMES:
        logger = logging.getLogger(name)
        logger.addHandler(handler)
        attached.append((logger, handler))
    push_relay_line(f"pipeline job {job_id} started", job_id=job_id)
    try:
        yield
    finally:
        push_relay_line(f"pipeline job {job_id} finished", job_id=job_id)
        for logger, h in attached:
            logger.removeHandler(h)
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
