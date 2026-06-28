"""DB-free tests for META door seam 3a (#23-26 bypass closure)."""

from __future__ import annotations

import inspect
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.modules.data_firewall.firewall import evaluate_market
from app.modules.data_firewall.signing import reset_signing_settings_cache
from app.modules.marketplaces.service import MarketplacePoolService
from app.modules.persist.meta_write import (
    build_dim_marketplace_fields,
    build_scrape_job_failed_fields,
)
from app.modules.scraper.pipeline import tick_orchestrator as tick_mod
from app.workers import reaper_tasks

BACKEND_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def _data_firewall_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATA_FIREWALL_SIGNING_SECRET", "unit-test-data-firewall-secret")
    reset_signing_settings_cache()
    yield
    reset_signing_settings_cache()


def _read_source(rel_path: str) -> str:
    return (BACKEND_ROOT / rel_path).read_text(encoding="utf-8")


def test_no_raw_update_scrape_jobs_at_sites() -> None:
    reaper = _read_source("app/workers/reaper_tasks.py")
    tick = _read_source("app/modules/scraper/pipeline/tick_orchestrator.py")
    assert 'UPDATE scrape_jobs' not in reaper
    assert "UPDATE scrape_jobs" not in tick


def test_no_raw_dim_marketplace_update_at_site_26() -> None:
    source = _read_source("app/modules/marketplaces/service.py")
    assert "update(DimMarketplace)" not in source


def test_failed_status_passes_structural_contract() -> None:
    now = datetime.now(tz=timezone.utc)
    fields = build_scrape_job_failed_fields(
        id=uuid4(),
        started_at=now,
        completed_at=now,
    )
    outcome = evaluate_market(
        fields,
        table="scrape_jobs",
        operation="update",
        db=MagicMock(),
    )
    assert outcome.passed is True
    assert fields["status"] == "failed"


def test_products_in_pool_passes_structural_contract() -> None:
    marketplace_id = uuid4()
    fields = build_dim_marketplace_fields(id=marketplace_id, products_in_pool=42)
    outcome = evaluate_market(
        fields,
        table="dim_marketplace",
        operation="update",
        db=MagicMock(),
    )
    assert outcome.passed is True


@pytest.mark.asyncio
@patch("app.workers.reaper_tasks.write_meta_async", new_callable=AsyncMock)
@patch.object(reaper_tasks, "_should_reap_job", return_value=(True, 999))
async def test_site_23_reaper_routes_per_id(
    _mock_should: MagicMock,
    mock_meta: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_meta.return_value = MagicMock(ok=True, no_target=False)
    now = datetime.now(tz=timezone.utc)
    job_id = uuid4()
    rows = [
        MagicMock(
            id=job_id,
            job_type="discovery",
            status="running",
            started_at=now,
            config={},
        ),
    ]
    engine = MagicMock()
    engine.dispose = AsyncMock()
    db = MagicMock()
    select_result = MagicMock()
    select_result.all.return_value = rows
    db.execute = AsyncMock(return_value=select_result)

    class _SessionCM:
        async def __aenter__(self):
            return db

        async def __aexit__(self, *_a):
            return False

    monkeypatch.setattr(reaper_tasks, "_make_session_factory", lambda: (engine, _SessionCM))

    await reaper_tasks._reap_orphan_jobs_async()

    mock_meta.assert_awaited_once()
    assert mock_meta.call_args.kwargs["table"] == "scrape_jobs"
    assert mock_meta.call_args.kwargs["operation"] == "update"
    assert mock_meta.call_args.kwargs["fields"]["status"] == "failed"


@pytest.mark.asyncio
@patch("app.modules.scraper.pipeline.tick_orchestrator.write_meta_async", new_callable=AsyncMock)
async def test_site_24_discovery_reap_select_then_meta(mock_meta: AsyncMock) -> None:
    mock_meta.return_value = MagicMock(ok=True, no_target=False)
    parent_id = uuid4()
    child_id = uuid4()
    now = datetime.now(tz=timezone.utc)
    db = MagicMock()
    select_result = MagicMock()
    select_result.all.return_value = [(child_id, now)]
    db.execute = AsyncMock(return_value=select_result)

    count = await tick_mod._reap_stale_children(db, parent_id)

    assert count == 1
    db.execute.assert_awaited_once()
    mock_meta.assert_awaited_once()
    assert mock_meta.call_args.kwargs["reject_source"] == "orchestrator_reap_discovery"


@pytest.mark.asyncio
@patch("app.modules.scraper.pipeline.tick_orchestrator.write_meta_async", new_callable=AsyncMock)
async def test_site_25_scrape_reap_select_then_meta(mock_meta: AsyncMock) -> None:
    mock_meta.return_value = MagicMock(ok=True, no_target=False)
    parent_id = uuid4()
    child_id = uuid4()
    now = datetime.now(tz=timezone.utc)
    db = MagicMock()
    select_result = MagicMock()
    select_result.all.return_value = [(child_id, now)]
    db.execute = AsyncMock(return_value=select_result)

    count = await tick_mod._reap_stale_scrape_children(db, parent_id)

    assert count == 1
    mock_meta.assert_awaited_once()
    assert mock_meta.call_args.kwargs["reject_source"] == "orchestrator_reap_scrape"


@pytest.mark.asyncio
@patch("app.modules.marketplaces.service.write_meta_async", new_callable=AsyncMock)
async def test_site_26_quota_routes_through_meta(mock_meta: AsyncMock) -> None:
    mock_meta.return_value = MagicMock(ok=True)
    marketplace_id = uuid4()
    db = MagicMock()
    db.execute = AsyncMock(
        return_value=MagicMock(all=MagicMock(return_value=[(marketplace_id, 7)])),
    )
    svc = MarketplacePoolService(db)
    await svc.recalculate_all_quotas()

    mock_meta.assert_awaited_once()
    assert mock_meta.call_args.kwargs["table"] == "dim_marketplace"
    assert mock_meta.call_args.kwargs["fields"]["products_in_pool"] == 7
    db.commit.assert_not_called()


def test_reap_helpers_avoid_async_session_commit() -> None:
    discovery_src = inspect.getsource(tick_mod._reap_stale_children)
    scrape_src = inspect.getsource(tick_mod._reap_stale_scrape_children)
    assert "db.commit" not in discovery_src
    assert "db.commit" not in scrape_src
    assert "write_meta_async" in discovery_src
    assert "write_meta_async" in scrape_src
