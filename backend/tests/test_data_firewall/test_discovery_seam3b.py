"""DB-free tests for discovery seam 3b (#27-32 cursor flush removal)."""

from __future__ import annotations

import inspect
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.modules.discovery import bfs_walker, cursor_store, sitemap_harvester
from app.modules.discovery.cursor_store import DISCOVERY_MP_WRITE_KEYS
from app.modules.discovery.orchestrator import (
    DiscoveryOrchestrator,
    _meta_update_marketplace_snapshot,
)
from app.modules.persist.meta_write import build_dim_marketplace_fields

BACKEND_ROOT = Path(__file__).resolve().parents[2]

CURSOR_SITE_FILES = (
    "app/modules/discovery/bfs_walker.py",
    "app/modules/discovery/sitemap_harvester.py",
    "app/modules/discovery/orchestrator.py",
)

INTERMEDIATE_CURSOR_KEYS = (
    "recon_frontier_state",
    "discovered_category_urls",
    "category_resume_index",
    "last_category_recon_at",
    "last_sitemap_harvest_at",
    "phase1_exhausted_streak",
    "sitemap_url",
    "sitemap_bad_harvest_streak",
)


def _read_source(rel_path: str) -> str:
    return (BACKEND_ROOT / rel_path).read_text(encoding="utf-8")


def test_no_db_flush_in_discovery_cursor_modules() -> None:
    """Sites #27-32: intermediate cursor paths must not call db.flush()."""
    for rel in CURSOR_SITE_FILES:
        source = _read_source(rel)
        assert "db.flush()" not in source, rel


def test_all_intermediate_cursor_keys_in_discovery_mp_write_keys() -> None:
    missing = [k for k in INTERMEDIATE_CURSOR_KEYS if k not in DISCOVERY_MP_WRITE_KEYS]
    assert missing == []


def test_publish_category_batch_updates_in_memory_cursor_only() -> None:
    mp = MagicMock()
    mp.id = uuid4()
    queue: deque[tuple[str, int]] = deque([("https://shop.example/cat", 1)])
    visited = {"https://shop.example"}
    listing_urls = [
        "https://shop.example/p/1",
        "https://shop.example/p/2",
    ]

    unique = bfs_walker._publish_category_batch(
        mp,
        listing_urls,
        queue,
        visited,
    )

    assert unique == listing_urls
    assert mp.discovered_category_urls == listing_urls
    assert mp.category_resume_index == 0
    assert mp.last_category_recon_at is not None
    assert mp.recon_frontier_state is not None


@pytest.mark.asyncio
async def test_run_category_bfs_budget_exhausted_preserves_frontier_in_memory() -> None:
    mp = MagicMock()
    mp.id = uuid4()
    mp.base_url = "https://shop.example/"
    mp.recon_frontier_state = {
        "queue": [["https://shop.example/a", 0]],
        "visited": ["https://shop.example/"],
        "listing_urls": [],
    }
    mp.discovered_category_urls = []
    mp.phase1_exhausted_streak = 0

    pool = MagicMock()
    pool.scrape_page_for_analysis = AsyncMock()
    db = AsyncMock()
    db.flush = AsyncMock()

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(
            "app.modules.discovery.bfs_walker.time.monotonic",
            lambda: 5000.0,
        )
        urls, exhausted = await bfs_walker.run_category_bfs(
            mp,
            pool,
            db,
            deadline_monotonic=4000.0,
        )

    assert urls == []
    assert exhausted is True
    assert isinstance(mp.recon_frontier_state, dict)
    db.flush.assert_not_awaited()


@pytest.mark.asyncio
async def test_harvest_sitemap_preserves_cursor_in_memory_no_flush() -> None:
    from app.modules.discovery.constants import SITEMAP_MIN_USEFUL_URLS

    mp = MagicMock()
    mp.id = uuid4()
    mp.base_url = "https://test-mp.example"
    mp.locale = "en"
    mp.last_sitemap_harvest_at = None
    mp.sitemap_url = None
    mp.sitemap_bad_harvest_streak = 0

    pool = MagicMock()
    pool.fetch_sitemap_candidates = AsyncMock(
        return_value=[f"https://test-mp.example/p/{i}" for i in range(12)],
    )
    db = AsyncMock()
    db.flush = AsyncMock()

    product_urls = [f"https://test-mp.example/product/{i}" for i in range(12)]

    async def fake_filter(urls, *, requires_js, scrape_tier, marketplace_locale=None, marketplace_id=None):
        return product_urls, {"mode": "full", "accepted": len(product_urls)}

    result = await sitemap_harvester.harvest_sitemap(
        mp,
        pool,
        db,
        filter_urls_by_role=fake_filter,
    )

    assert len(result) >= SITEMAP_MIN_USEFUL_URLS
    assert mp.last_sitemap_harvest_at is not None
    db.flush.assert_not_awaited()


def test_site_32_timeout_block_has_no_flush_after_cursor_set() -> None:
    source = _read_source("app/modules/discovery/orchestrator.py")
    marker = 'errors.append("sitemap_phase_timeout")'
    start = source.index(marker)
    block = source[start : start + 800]
    assert "set_last_sitemap_harvest_at" in block
    assert "db.flush()" not in block


def test_site_32_timeout_cursor_set_preserves_in_memory_value() -> None:
    from datetime import timedelta

    from app.modules.discovery.constants import (
        SITEMAP_STALE_DAYS,
        SITEMAP_TIMEOUT_COOLDOWN_HOURS,
    )

    mp = MagicMock()
    mp.id = uuid4()
    now = datetime.now(tz=timezone.utc)
    retry_offset = timedelta(
        days=SITEMAP_STALE_DAYS,
        hours=-SITEMAP_TIMEOUT_COOLDOWN_HOURS,
    )
    cursor_store.set_last_sitemap_harvest_at(mp, now - retry_offset)
    assert mp.last_sitemap_harvest_at == now - retry_offset


@pytest.mark.asyncio
@patch(
    "app.modules.discovery.orchestrator.write_pool_dtos_sync",
    return_value=MagicMock(inserted=2, rejected=0),
)
async def test_gated_pool_batch_path_unchanged(mock_pool_sync: MagicMock) -> None:
    mp_id = uuid4()
    db = AsyncMock()
    orch = DiscoveryOrchestrator(db, MagicMock())

    from app.modules.discovery.gate_persist import PoolInsertDTO

    dtos = [
        PoolInsertDTO(
            marketplace_id=mp_id,
            dim_product={"url": "https://shop.example/p/1"},
            fact_listing={"url_hash": "h1"},
        ),
    ]
    result = await orch._write_pool_batch(mp_id, dtos)

    mock_pool_sync.assert_called_once_with(dtos)
    assert result.inserted == 2


@pytest.mark.asyncio
@patch(
    "app.modules.discovery.orchestrator.write_meta_async",
    new_callable=AsyncMock,
    return_value=MagicMock(ok=True),
)
async def test_final_snapshot_writes_all_cursor_keys(mock_meta: AsyncMock) -> None:
    now = datetime.now(tz=timezone.utc)
    mp = MagicMock()
    mp.id = uuid4()
    mp.base_url = "https://shop.example"
    mp.last_sitemap_harvest_at = now
    mp.sitemap_url = "https://shop.example/sitemap.xml"
    mp.recon_frontier_state = {"queue": [], "visited": [], "listing_urls": []}
    mp.discovered_category_urls = ["https://shop.example/p/1"]
    mp.category_resume_index = 0
    mp.sitemap_resume_offset = 0
    mp.sitemap_bad_harvest_streak = 0
    mp.phase1_exhausted_streak = 0
    mp.last_discovery_at = now
    mp.last_discovery_status = "completed"
    mp.last_discovery_products_found = 5
    mp.products_in_pool = 5
    mp.last_category_recon_at = now

    await _meta_update_marketplace_snapshot(mp)

    mock_meta.assert_awaited_once()
    fields = mock_meta.call_args.kwargs["fields"]
    assert mock_meta.call_args.kwargs["table"] == "dim_marketplace"
    for key in DISCOVERY_MP_WRITE_KEYS:
        assert key in fields
    expected = build_dim_marketplace_fields(id=mp.id, **cursor_store.snapshot_meta_columns(mp))
    assert fields == expected


def test_discover_one_marketplace_session_has_no_commit() -> None:
    source = _read_source("app/modules/scraper/tasks.py")
    discover_block = source.split("def discover_one_marketplace", 1)[1].split(
        "def discover_single_marketplace",
        1,
    )[0]
    assert "db.commit" not in discover_block
    assert "await db.commit" not in discover_block


def test_publish_category_batch_does_not_import_gate_persist() -> None:
    source = inspect.getsource(bfs_walker._publish_category_batch)
    assert "write_pool" not in source
    assert "evaluate_market" not in source
    assert "gate_persist" not in source
