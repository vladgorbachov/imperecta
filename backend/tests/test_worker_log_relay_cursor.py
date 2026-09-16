"""Relay cursor self-healing + run-boundary lines (no real Redis)."""

from __future__ import annotations

import json
from unittest.mock import patch

from app.modules.scraper.pipeline import worker_log_relay as relay


class _FakeRedis:
    def __init__(self, rows):
        self._rows = [json.dumps(r) for r in rows]

    def lrange(self, _key, _start, _end):
        return list(self._rows)


def _rows(*seqs):
    return [{"seq": s, "at": "2026-09-16T00:00:00+00:00", "line": f"line {s}", "job_id": None} for s in seqs]


def test_normal_tail_after_cursor():
    with patch.object(relay, "_get_redis", return_value=_FakeRedis(_rows(1, 2, 3, 4))):
        out = relay.fetch_relay_lines(after=2, limit=50)
    assert [r["seq"] for r in out["lines"]] == [3, 4]
    assert out["next_cursor"] == 4


def test_desynced_cursor_returns_tail_instead_of_freezing():
    """Client cursor ahead of every buffered seq (seq counter reset) -> tail."""
    with patch.object(relay, "_get_redis", return_value=_FakeRedis(_rows(1, 2, 3))):
        out = relay.fetch_relay_lines(after=1200, limit=2)
    assert [r["seq"] for r in out["lines"]] == [2, 3]
    assert out["next_cursor"] == 3  # corrected, polling continues


def test_empty_buffer_keeps_cursor():
    with patch.object(relay, "_get_redis", return_value=_FakeRedis([])):
        out = relay.fetch_relay_lines(after=7, limit=10)
    assert out["lines"] == []
    assert out["next_cursor"] == 7
