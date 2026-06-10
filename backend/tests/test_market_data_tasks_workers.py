"""
M3b worker-relocation tests for the market_data module.

Verifies that Celery task definitions now live in Tier-2 `app.workers.*`, that
task names are preserved verbatim (so beat schedules and `/markets/ingest`
remain compatible), that the Celery registry no longer includes the retired
Tier-1 path, and that each wrapper dispatches to the Tier-1 `IngestionService`
contract without leaking domain logic into Tier-2.
"""

import importlib
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.workers import market_data_tasks as workers_module
from app.workers.celery_app import celery_app
from app.workers.market_data_tasks import (
    FACT_TABLE_NAMES,
    ingest_commodities,
    ingest_market_data,
)


def test_market_data_tasks_live_in_workers() -> None:
    """Tier-2 module imports cleanly; Tier-1 tasks.py is retired."""
    importlib.import_module("app.workers.market_data_tasks")
    with pytest.raises(ImportError):
        importlib.import_module("app.modules.market_data.tasks")


def test_task_names_preserved() -> None:
    """Beat / .delay() parity: task names must match the pre-M3b strings."""
    assert ingest_market_data.name == "ingest_market_data"
    assert ingest_commodities.name == "ingest_commodities"


def test_celery_include_updated() -> None:
    """celery_app.conf.include points at the worker-tier module, not the retired Tier-1 path."""
    include = list(celery_app.conf.include)
    assert "app.workers.market_data_tasks" in include
    assert "app.modules.market_data.tasks" not in include


def test_fact_table_names_present() -> None:
    """FACT_TABLE_NAMES survives the move and remains a 4-tuple of strings."""
    assert isinstance(FACT_TABLE_NAMES, tuple)
    assert len(FACT_TABLE_NAMES) == 4
    assert all(isinstance(name, str) and name for name in FACT_TABLE_NAMES)


def test_ingest_market_data_wrapper_calls_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    """The wrapper builds a session and dispatches to IngestionService.ingest_all."""
    engine_mock = MagicMock()
    engine_mock.dispose = AsyncMock()
    session = MagicMock()
    session_factory = MagicMock(return_value=_async_cm(session))
    monkeypatch.setattr(workers_module, "_make_session_factory", lambda: (engine_mock, session_factory))

    ingest_all_mock = AsyncMock(return_value={"forex": 2, "crypto": 3, "commodities": 1})
    monkeypatch.setattr(
        "app.modules.market_data.ingestion.IngestionService.ingest_all",
        ingest_all_mock,
    )

    result = ingest_market_data.run()

    ingest_all_mock.assert_awaited_once_with(include_commodities=True)
    engine_mock.dispose.assert_awaited_once()
    assert result["status"] == "ok"
    assert result["counts"] == {"forex": 2, "crypto": 3, "commodities": 1}
    assert result["fact_tables"] == list(FACT_TABLE_NAMES)


def test_ingest_commodities_wrapper_calls_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    """The wrapper dispatches to IngestionService.ingest_commodities_only."""
    engine_mock = MagicMock()
    engine_mock.dispose = AsyncMock()
    session = MagicMock()
    session_factory = MagicMock(return_value=_async_cm(session))
    monkeypatch.setattr(workers_module, "_make_session_factory", lambda: (engine_mock, session_factory))

    only_mock = AsyncMock(return_value=4)
    monkeypatch.setattr(
        "app.modules.market_data.ingestion.IngestionService.ingest_commodities_only",
        only_mock,
    )

    result = ingest_commodities.run()

    only_mock.assert_awaited_once_with()
    engine_mock.dispose.assert_awaited_once()
    assert result["status"] == "ok"
    assert result["commodities"] == 4
    assert result["fact_tables"] == list(FACT_TABLE_NAMES)


def test_ingest_wrapper_returns_error_payload_on_contract_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Contract exceptions are surfaced as {'status': 'error', ...} (no re-raise)."""
    engine_mock = MagicMock()
    engine_mock.dispose = AsyncMock()
    session = MagicMock()
    session_factory = MagicMock(return_value=_async_cm(session))
    monkeypatch.setattr(workers_module, "_make_session_factory", lambda: (engine_mock, session_factory))
    monkeypatch.setattr(
        "app.modules.market_data.ingestion.IngestionService.ingest_all",
        AsyncMock(side_effect=RuntimeError("DB unreachable")),
    )

    result = ingest_market_data.run()
    assert result["status"] == "error"
    assert "DB unreachable" in result["message"]
    engine_mock.dispose.assert_awaited_once()


@pytest.mark.asyncio
async def test_ingest_endpoint_dispatches_to_worker_task(monkeypatch: pytest.MonkeyPatch) -> None:
    """/markets/ingest still enqueues via the new worker-tier task path."""
    fake_task = SimpleNamespace(id="abc-123")
    delay_mock = MagicMock(return_value=fake_task)
    monkeypatch.setattr(
        "app.workers.market_data_tasks.ingest_market_data.delay",
        delay_mock,
    )

    from app.modules.market_data.api import trigger_ingest

    superuser = SimpleNamespace(id="superuser-id", is_superuser=True)
    payload = await trigger_ingest(superuser=superuser)

    delay_mock.assert_called_once_with()
    assert payload == {"status": "enqueued", "task_id": "abc-123"}


def _async_cm(target):
    """Build an async context-manager double that yields `target`."""

    class _AsyncCM:
        async def __aenter__(self_inner):
            return target

        async def __aexit__(self_inner, exc_type, exc, tb):
            return False

    return _AsyncCM()
