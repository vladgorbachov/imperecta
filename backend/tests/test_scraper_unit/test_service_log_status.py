"""Unit tests for GlobalScrapeService log status mapping and small helpers."""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import MagicMock

import pytest

from app.modules.scraper.extractors import ExtractedProduct
from app.modules.scraper.scraper_pool import PoolScrapeResult
from app.modules.scraper.service import (
    GlobalScrapeService,
    _compute_price_change_pct,
    _needs_scrape_logs_status_column_repair,
    _optional_in_stock,
    _payload_has_product_name_field,
    _previous_price_snapshot,
)


def test_optional_in_stock_variants():
    assert _optional_in_stock(None) is None

    @dataclass
    class P:
        in_stock: bool | str | None

    assert _optional_in_stock(P(in_stock=True)) is True
    assert _optional_in_stock(P(in_stock="x")) is None


def test_payload_has_product_name_field():
    @dataclass
    class WithName:
        product_name: str | None = None
        title: str | None = None

    assert _payload_has_product_name_field(WithName()) is True
    assert _payload_has_product_name_field(ExtractedProduct()) is False


def test_determine_log_status_failed_variants():
    svc = GlobalScrapeService(MagicMock(), MagicMock())
    r = PoolScrapeResult(success=False, url="u", error="parse_error:bad")
    assert svc._determine_log_status(r) == "parse_error"
    r = PoolScrapeResult(success=False, url="u", error="price_not_found")
    assert svc._determine_log_status(r) == "price_not_found"
    r = PoolScrapeResult(success=False, url="u", error="not_found page")
    assert svc._determine_log_status(r) == "not_found"
    r = PoolScrapeResult(success=False, url="u", error="captcha block")
    assert svc._determine_log_status(r) == "captcha"
    r = PoolScrapeResult(success=False, url="u", error="blocked")
    assert svc._determine_log_status(r) == "blocked"
    r = PoolScrapeResult(success=False, url="u", error="timeout:httpx")
    assert svc._determine_log_status(r) == "timeout"
    r = PoolScrapeResult(success=False, url="u", error="fetch_failed:x")
    assert svc._determine_log_status(r) == "error"
    r = PoolScrapeResult(success=False, url="u", error="unknown")
    assert svc._determine_log_status(r) == "error"
    r = PoolScrapeResult(success=False, url="u", error="exception:RuntimeError:fail")
    assert svc._determine_log_status(r) == "technical_error"
    r = PoolScrapeResult(success=False, url="u", error="price_overflow")
    assert svc._determine_log_status(r) == "technical_error"


def test_determine_log_status_success_paths():
    svc = GlobalScrapeService(MagicMock(), MagicMock())
    empty = PoolScrapeResult(success=True, url="u", data=ExtractedProduct(), is_empty=True)
    assert svc._determine_log_status(empty) == "missing_critical_data"

    data = ExtractedProduct(title="T", price=1.0, currency="USD")
    r = PoolScrapeResult(
        success=True,
        url="u",
        data=data,
        missing_fields=["currency"],
    )
    assert svc._determine_log_status(r, data=data) == "missing_critical_data"

    # Legacy branch requires payload from result.data while data kwarg is None.
    legacy = PoolScrapeResult(
        success=True,
        url="u",
        data=ExtractedProduct(title="T", price=1.0, currency="USD"),
    )
    assert (
        svc._determine_log_status(legacy, data=None, has_title=False, has_price=True)
        == "missing_critical_data"
    )
    assert (
        svc._determine_log_status(legacy, data=None, has_title=True, has_price=False)
        == "price_not_found"
    )

    ok = PoolScrapeResult(success=True, url="u", data=data, is_partial=False)
    assert svc._determine_log_status(ok, data=data) == "success"

    partial = PoolScrapeResult(success=True, url="u", data=data, is_partial=True)
    assert svc._determine_log_status(partial, data=data, is_partial=True) == "missing_critical_data"


def test_categorize_error_branches():
    svc = GlobalScrapeService(MagicMock(), MagicMock())
    assert svc._categorize_error("") is None
    assert svc._categorize_error("fetch failed") == "network"
    assert svc._categorize_error("parse extract") == "parse"
    assert svc._categorize_error("timeout") == "network"
    assert svc._categorize_error("blocked captcha") == "auth"
    assert svc._categorize_error("rate limited") == "rate_limit"
    assert svc._categorize_error("weird") == "parse"


def test_previous_price_snapshot():
    from uuid import uuid4

    lid = uuid4()
    session = MagicMock()
    row = MagicMock()
    row.scalar_one_or_none.return_value = 9.5
    session.execute.return_value = row
    assert _previous_price_snapshot(session, lid, 20260101) == 9.5


def test_compute_price_change_pct_bounds():
    assert _compute_price_change_pct(None, 10.0) is None
    assert _compute_price_change_pct(0.0, 10.0) is None
    assert _compute_price_change_pct(100.0, 120.0) == 20.0
    # Numeric(8,4) cap protection: values above 9999.9999 become NULL.
    assert _compute_price_change_pct(1.0, 1000.0) is None


def test_detect_status_column_drift_error():
    err = Exception(
        "(psycopg2.errors.StringDataRightTruncation) value too long for type character varying(20)"
    )
    assert _needs_scrape_logs_status_column_repair(err) is True


def test_recalculate_analytics_noop():
    from uuid import uuid4

    svc = GlobalScrapeService(MagicMock(), MagicMock())
    svc.recalculate_analytics(uuid4())  # no exception


def test_get_stale_products_mock_session():
    from uuid import uuid4

    lid = uuid4()
    session = MagicMock()
    session.execute.return_value.all.return_value = [(lid,)]
    svc = GlobalScrapeService(session, MagicMock())
    assert svc.get_stale_products(10) == [lid]
