"""OBSERVABILITY-FIX: PipelineWorkerLogHandler concurrency + throttle + registry.

These tests pin the contract that O4c orphaned and the first real-PG run
exposed:

- The handler must stamp emitted records with its OWN ``job_id`` (per-instance,
  not the racy ``_active_job_id`` module global) so two children running in one
  worker process don't cross-stamp each other's lines.
- The handler must throttle so a 25k-fetch scrape phase can't flood Upstash.
- Concurrent ticks/children of the SAME parent must share ONE handler via the
  ref-counted registry (no double-emit per captured record); children of
  DIFFERENT parents must get DIFFERENT handlers (correct isolation).
"""

from __future__ import annotations

import logging
from unittest.mock import patch
from uuid import UUID, uuid4

from app.modules.scraper.pipeline import worker_log_relay as wlr
from app.modules.scraper.pipeline.worker_log_relay import (
    PipelineWorkerLogHandler,
    pipeline_worker_log_relay,
)


def _make_record(message: str = "fetch ok") -> logging.LogRecord:
    return logging.LogRecord(
        name="app.modules.scraper.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg=message,
        args=None,
        exc_info=None,
    )


def test_handler_stamps_its_own_job_id_not_module_global() -> None:
    """Per-instance job_id is passed explicitly to push_relay_line — handler
    does NOT consult ``_active_job_id``, so two concurrent children in the
    same process can each stamp their own parent without racing the global.
    """
    parent_a = UUID("11111111-1111-1111-1111-111111111111")
    pushed: list[tuple[str, UUID | None]] = []

    def fake_push(line: str, *, job_id: UUID | None = None) -> int:
        pushed.append((line, job_id))
        return 1

    handler = PipelineWorkerLogHandler(job_id=parent_a, min_interval_s=0.0)
    handler.setFormatter(logging.Formatter(fmt="%(message)s"))

    # Set the module global to a DIFFERENT id; the handler must ignore it.
    wlr.set_active_pipeline_job(uuid4())
    try:
        with patch.object(wlr, "push_relay_line", side_effect=fake_push):
            handler.emit(_make_record("hello"))
    finally:
        wlr.set_active_pipeline_job(None)

    assert pushed == [("hello", parent_a)]


def test_handler_throttles_within_window() -> None:
    """Two records arriving inside ``min_interval_s`` produce ONE push (the
    second is dropped). Throttling is intentional + lossy — the live monitor
    only needs heartbeat granularity, the structlog stream remains complete.
    """
    pushed: list[tuple[str, UUID | None]] = []

    def fake_push(line: str, *, job_id: UUID | None = None) -> int:
        pushed.append((line, job_id))
        return 1

    times = iter([100.0, 100.1, 100.6])

    handler = PipelineWorkerLogHandler(job_id=uuid4(), min_interval_s=0.5)
    handler.setFormatter(logging.Formatter(fmt="%(message)s"))

    with patch.object(wlr.time, "monotonic", side_effect=lambda: next(times)):
        with patch.object(wlr, "push_relay_line", side_effect=fake_push):
            handler.emit(_make_record("a"))
            handler.emit(_make_record("b"))
            handler.emit(_make_record("c"))

    assert [line for line, _ in pushed] == ["a", "c"]


def test_same_parent_concurrent_cms_share_one_handler() -> None:
    """Two ``pipeline_worker_log_relay`` CMs entered for the SAME parent_id
    use the SAME registered handler (ref-counted). Only the outer exit
    detaches it. Each captured record emits ONCE, not twice.
    """
    parent_id = UUID("22222222-2222-2222-2222-222222222222")
    pushed: list[str] = []

    def fake_push(line: str, *, job_id: UUID | None = None) -> int:
        pushed.append(line)
        return 1

    # The relay logger inherits root WARNING by default; raise it to INFO
    # so the sentinel record reaches the handler under test (the actual
    # production worker has Celery's logging config in place, INFO-enabled).
    relay_logger = logging.getLogger("app.modules.scraper")
    prev_level = relay_logger.level
    relay_logger.setLevel(logging.INFO)
    try:
        with patch.object(wlr, "push_relay_line", side_effect=fake_push):
            with pipeline_worker_log_relay(parent_id):
                entry = wlr._handler_registry[parent_id]
                outer_handler, count_after_outer = entry
                assert count_after_outer == 1
                with pipeline_worker_log_relay(parent_id):
                    entry2 = wlr._handler_registry[parent_id]
                    assert entry2[0] is outer_handler
                    assert entry2[1] == 2
                    # Both CMs entered; the module loggers carry the SAME
                    # single handler (not two). Emit one INFO record on a
                    # relay logger and assert exactly ONE push (no duplicate-
                    # handler emit). Reset the throttle window so the inner
                    # emit isn't suppressed (we test throttling separately).
                    outer_handler._last_emit_monotonic = 0.0
                    pushed.clear()
                    relay_logger.info("sentinel-line")
                    count_for_record = sum(
                        1 for line in pushed if "sentinel-line" in line
                    )
                    assert count_for_record == 1
                # After the inner CM exits: handler still registered (count=1).
                assert wlr._handler_registry[parent_id][1] == 1
            # After outer CM exits: handler evicted entirely.
            assert parent_id not in wlr._handler_registry
    finally:
        relay_logger.setLevel(prev_level)


def test_different_parents_get_separate_handlers() -> None:
    parent_a = UUID("33333333-3333-3333-3333-333333333333")
    parent_b = UUID("44444444-4444-4444-4444-444444444444")

    with patch.object(wlr, "push_relay_line", return_value=1):
        with pipeline_worker_log_relay(parent_a):
            with pipeline_worker_log_relay(parent_b):
                handler_a, count_a = wlr._handler_registry[parent_a]
                handler_b, count_b = wlr._handler_registry[parent_b]
                assert count_a == 1 and count_b == 1
                assert handler_a is not handler_b
                # Each handler stamps its own parent.
                assert handler_a._job_id == parent_a
                assert handler_b._job_id == parent_b

    assert parent_a not in wlr._handler_registry
    assert parent_b not in wlr._handler_registry
