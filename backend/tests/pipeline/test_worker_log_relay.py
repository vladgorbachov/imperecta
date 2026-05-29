"""Tests for Redis worker log relay buffer."""

from __future__ import annotations

from unittest.mock import MagicMock, patch
from uuid import UUID

from app.modules.scraper.pipeline.worker_log_relay import (
    fetch_relay_lines,
    push_relay_line,
)


def test_push_and_fetch_relay_lines_in_order() -> None:
    job_id = UUID("cfcc3988-bd3e-46b3-927f-fa181221e246")
    fake = MagicMock()
    fake.incr.side_effect = [1, 2, 3]
    fake.lrange.return_value = []

    with patch(
        "app.modules.scraper.pipeline.worker_log_relay._get_redis",
        return_value=fake,
    ):
        push_relay_line("line one", job_id=job_id)
        push_relay_line("line two", job_id=job_id)

    fake.rpush.assert_called()
    fake.ltrim.assert_called_with("pipeline:worker_deploy_log", -500, -1)


def test_fetch_relay_lines_after_cursor() -> None:
    fake = MagicMock()
    fake.lrange.return_value = [
        '{"seq":1,"at":"t1","line":"old","job_id":null}',
        '{"seq":2,"at":"t2","line":"new","job_id":null}',
    ]
    with patch(
        "app.modules.scraper.pipeline.worker_log_relay._get_redis",
        return_value=fake,
    ):
        payload = fetch_relay_lines(after=1, limit=10)

    assert len(payload["lines"]) == 1
    assert payload["lines"][0]["line"] == "new"
    assert payload["next_cursor"] == 2
