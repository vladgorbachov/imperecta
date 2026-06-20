"""B2 scrape_logs diagnostic resolution tests."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

import app.modules.scraper.scraper_pool as sp
from app.modules.scraper.extractors import ExtractedProduct
from app.modules.scraper.scraper_pool import PoolScrapeResult, ScraperPool
from app.modules.scraper.service import (
    GlobalScrapeService,
    _categorize_from_log_status,
    _resolve_scrape_log_diagnostics,
)


def test_error_message_not_null_on_forced_status():
    """Gate-forced rejection with success=True must not persist NULL error_message."""
    result = PoolScrapeResult(
        success=True,
        url="https://shop.example/p/1",
        error=None,
        data=ExtractedProduct(title="T", price=1.0, currency="SEK"),
    )
    msg, cat = _resolve_scrape_log_diagnostics(
        result=result,
        log_status="currency_rejected",
        gate_skip_reason="currency_country_mismatch",
    )
    assert msg is not None
    assert msg == "gate:currency_country_mismatch"
    assert cat == "data_quality"


def test_error_message_status_fallback_when_no_gate_reason():
    result = PoolScrapeResult(success=True, url="u", error=None)
    msg, cat = _resolve_scrape_log_diagnostics(
        result=result,
        log_status="currency_rejected",
        gate_skip_reason=None,
    )
    assert msg == "status:currency_rejected"
    assert cat == "data_quality"


def test_error_message_preserves_result_error():
    result = PoolScrapeResult(success=False, url="u", error="parse_error:ValueError:bad")
    msg, cat = _resolve_scrape_log_diagnostics(
        result=result,
        log_status="parse_error",
    )
    assert msg == "parse_error:ValueError:bad"
    assert cat == "parse"


def test_error_category_from_status_mapping():
    assert _categorize_from_log_status("parse_error") == "parse"
    assert _categorize_from_log_status("currency_rejected") == "data_quality"
    assert _categorize_from_log_status("missing_critical_data") == "data_quality"
    assert _categorize_from_log_status("technical_error") == "technical"
    assert _categorize_from_log_status("success") is None


def test_success_no_change_leaves_error_message_none():
    result = PoolScrapeResult(success=True, url="u", error=None)
    msg, cat = _resolve_scrape_log_diagnostics(
        result=result,
        log_status="no_change",
    )
    assert msg is None
    assert cat is None


@pytest.mark.asyncio
async def test_extract_error_includes_message(monkeypatch):
    pool = ScraperPool()

    async def fake_layer(backend_id, url: str, **kwargs):
        return "<html>body</html>", None

    def boom(*_a, **_k):
        raise ValueError("parse-detail")

    monkeypatch.setattr(pool, "_fetch_layer_with_retries", fake_layer)
    monkeypatch.setattr(sp, "merge_and_finalize", boom)
    monkeypatch.setattr(
        "app.modules.scraper.scraper_pool.capture_exception_if_initialized",
        MagicMock(),
    )
    r = await pool.scrape_product("https://shop.example/p/2")
    assert not r.success
    assert r.error is not None
    assert "ValueError" in r.error
    assert "parse-detail" in r.error


def test_categorize_error_branches_unchanged():
    svc = GlobalScrapeService(MagicMock(), MagicMock())
    assert svc._categorize_error("") is None
    assert svc._categorize_error("fetch failed") == "network"
    assert svc._categorize_error("parse extract") == "parse"
