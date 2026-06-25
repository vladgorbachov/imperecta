"""Pure-logic tests for honest scrape outcome rollup in complete_pipeline_job."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.modules.scraper.pipeline.job_completion import complete_pipeline_job


@pytest.mark.asyncio
async def test_complete_pipeline_job_honest_failed_excludes_filtered_and_unchanged():
    """job.failed counts only real failures; not_a_product and no_change are separate."""
    parent_id = uuid4()
    child_id = uuid4()
    mp_id = uuid4()

    job = MagicMock()
    job.id = parent_id
    job.config = {"metadata": {}}
    job.status = "running"

    child_result = MagicMock()
    child_result.all.return_value = [(child_id,)]

    log_rows = [
        SimpleNamespace(marketplace_id=mp_id, status="success", count=10),
        SimpleNamespace(marketplace_id=mp_id, status="no_change", count=5),
        SimpleNamespace(marketplace_id=mp_id, status="not_a_product", count=7),
        SimpleNamespace(marketplace_id=mp_id, status="error", count=2),
        SimpleNamespace(marketplace_id=mp_id, status="timeout", count=1),
    ]
    log_result = MagicMock()
    log_result.__iter__ = MagicMock(return_value=iter(log_rows))

    db = MagicMock()
    db.execute = AsyncMock(side_effect=[child_result, log_result])
    db.commit = AsyncMock()

    metadata = await complete_pipeline_job(
        db,
        job,
        discovery_ms=0,
        scrape_ms=100,
        persist_ms=0,
        per_marketplace_seed={
            mp_id: {
                "marketplace_id": str(mp_id),
                "domain": "shop.example",
                "listings_created": 0,
                "prices_saved": 0,
                "errors_count": 0,
                "duration_ms": 100,
                "status": "completed",
            }
        },
        hard_error=None,
    )

    mp = metadata["per_marketplace"][0]
    assert mp["successful"] == 10
    assert mp["unchanged"] == 5
    assert mp["filtered"] == 7
    assert mp["failed"] == 3
    assert mp["prices_saved"] == 10
    assert mp["errors_count"] == 3

    summary = metadata["summary"]
    assert summary["successful"] == 10
    assert summary["unchanged"] == 5
    assert summary["filtered"] == 7
    assert summary["failed"] == 3
    assert summary["total"] == 25
    assert summary["prices_saved"] == 10
    assert summary["errors_count"] == 3

    assert job.successful == 10
    assert job.failed == 3


@pytest.mark.asyncio
async def test_complete_pipeline_job_preserves_discovery_errors_in_errors_count():
    """Discovery-phase errors stay in errors_count; job.failed is scrape failures only."""
    parent_id = uuid4()
    child_id = uuid4()
    mp_id = uuid4()

    job = MagicMock()
    job.id = parent_id
    job.config = {"metadata": {}}
    job.status = "running"

    child_result = MagicMock()
    child_result.all.return_value = [(child_id,)]

    log_rows = [
        SimpleNamespace(marketplace_id=mp_id, status="success", count=2),
        SimpleNamespace(marketplace_id=mp_id, status="parse_error", count=1),
    ]
    log_result = MagicMock()
    log_result.__iter__ = MagicMock(return_value=iter(log_rows))

    db = MagicMock()
    db.execute = AsyncMock(side_effect=[child_result, log_result])
    db.commit = AsyncMock()

    metadata = await complete_pipeline_job(
        db,
        job,
        discovery_ms=50,
        scrape_ms=50,
        persist_ms=0,
        per_marketplace_seed={
            mp_id: {
                "marketplace_id": str(mp_id),
                "domain": "shop.example",
                "listings_created": 4,
                "prices_saved": 0,
                "errors_count": 2,
                "duration_ms": 50,
                "status": "completed",
            }
        },
        hard_error=None,
    )

    mp = metadata["per_marketplace"][0]
    assert mp["errors_count"] == 3
    assert mp["failed"] == 1
    assert metadata["summary"]["errors_count"] == 3
    assert job.failed == 1
