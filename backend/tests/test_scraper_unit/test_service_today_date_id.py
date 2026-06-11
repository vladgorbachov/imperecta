"""Tests for _today_date_id (mock Session; no DB)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.modules.scraper.service import _today_date_id


def test_today_date_id_existing_row(monkeypatch):
    from datetime import datetime, timezone

    fixed = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)

    class _DT:
        @staticmethod
        def now(tz=None):
            return fixed

    monkeypatch.setattr("app.modules.ingestion.service.datetime", _DT)

    session = MagicMock()
    session.execute.return_value.scalar_one_or_none.return_value = 20260115
    assert _today_date_id(session) == 20260115


def test_today_date_id_upsert_path(monkeypatch):
    from datetime import datetime, timezone

    fixed = datetime(2026, 3, 10, 12, 0, 0, tzinfo=timezone.utc)

    class _DT:
        @staticmethod
        def now(tz=None):
            return fixed

    monkeypatch.setattr("app.modules.ingestion.service.datetime", _DT)

    session = MagicMock()
    first = MagicMock()
    first.scalar_one_or_none.return_value = None
    third = MagicMock()
    third.scalar_one_or_none.return_value = 20260310
    session.execute.side_effect = [first, MagicMock(), third]
    session.flush = MagicMock()

    assert _today_date_id(session) == 20260310


def test_today_date_id_raises_when_still_missing(monkeypatch):
    from datetime import datetime, timezone

    fixed = datetime(2026, 4, 1, 12, 0, 0, tzinfo=timezone.utc)

    class _DT:
        @staticmethod
        def now(tz=None):
            return fixed

    monkeypatch.setattr("app.modules.ingestion.service.datetime", _DT)

    session = MagicMock()
    first = MagicMock()
    first.scalar_one_or_none.return_value = None
    third = MagicMock()
    third.scalar_one_or_none.return_value = None
    session.execute.side_effect = [first, MagicMock(), third]
    session.flush = MagicMock()

    with pytest.raises(RuntimeError, match="dim_date row missing"):
        _today_date_id(session)
