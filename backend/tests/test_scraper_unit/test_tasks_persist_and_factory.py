"""tasks.py: _persist_technical_error_log failure path and session factory."""

from __future__ import annotations

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.modules.scraper import tasks as scraper_tasks


def test_persist_technical_error_log_commit_raises():
    session = MagicMock()
    session.get.return_value = MagicMock(
        id=uuid4(),
        marketplace_id=uuid4(),
        external_url="https://x.com",
    )
    session.commit.side_effect = RuntimeError("db down")
    session.rollback = MagicMock()

    with patch.object(scraper_tasks, "sync_session_factory", return_value=session):
        scraper_tasks._persist_technical_error_log(uuid4(), "trace")
    session.rollback.assert_called()


@pytest.mark.asyncio
async def test_make_session_factory_returns_tuple():
    engine, factory = scraper_tasks._make_session_factory()
    try:
        assert engine is not None and factory is not None
    finally:
        await engine.dispose()
