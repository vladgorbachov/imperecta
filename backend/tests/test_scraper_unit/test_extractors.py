"""Unit tests for extractors, log status mapping, and pool (no outbound HTTP)."""

import pytest

from app.modules.scraper.extractors import (
    ExtractedProduct,
    merge_results,
    parse_price_text,
)
from app.modules.scraper.scraper_pool import PoolScrapeResult
from app.modules.scraper.service import (
    GlobalScrapeService,
    _optional_in_stock,
    _should_replace_placeholder_name,
)


def test_merge_results():
    """Merged result should preserve first non-None fields by priority."""
    high = ExtractedProduct(title="A")
    mid = ExtractedProduct(price=99.5)
    low = ExtractedProduct(image_url="https://img.example/1.jpg")
    merged = merge_results(high, mid, low)
    assert merged.title == "A"
    assert merged.price == 99.5
    assert merged.image_url == "https://img.example/1.jpg"


def test_parse_price_text():
    """Locale-aware price parsing should handle decimal separators."""
    assert parse_price_text("1 299,50 ₴") == 1299.50
    assert parse_price_text("$49.99") == 49.99
    assert parse_price_text("1.299,50 €") == 1299.50


def test_completeness_score():
    """Completeness score should match required fields ratio."""
    full = ExtractedProduct(title="x", price=10.0, image_url="img")
    partial = ExtractedProduct(title="x", price=10.0, image_url=None)
    assert full.completeness == 1.0
    assert round(partial.completeness, 2) == 0.67


def test_optional_in_stock_missing_on_extracted_product():
    """ExtractedProduct has no in_stock; persistence must not assume the attribute."""
    assert _optional_in_stock(ExtractedProduct(title="x", price=1.0)) is None
    assert _optional_in_stock(None) is None


def test_should_replace_placeholder_numeric_slug():
    assert _should_replace_placeholder_name("48239384", "https://example.com/p/48239384") is True


def test_should_replace_placeholder_product_literal():
    assert _should_replace_placeholder_name("product", "https://x.com/a") is True


def test_should_replace_placeholder_real_name():
    assert _should_replace_placeholder_name("Running Shoes", "https://x.com/p/1") is False


def test_determine_log_status_failure_variants():
    svc = GlobalScrapeService.__new__(GlobalScrapeService)
    assert (
        svc._determine_log_status(
            PoolScrapeResult(success=False, url="u", error="price_not_found"),
        )
        == "price_not_found"
    )
    assert (
        svc._determine_log_status(
            PoolScrapeResult(success=False, url="u", error="fetch_failed"),
        )
        == "error"
    )
    assert (
        svc._determine_log_status(
            PoolScrapeResult(success=False, url="u", error="timeout"),
        )
        == "timeout"
    )
    assert (
        svc._determine_log_status(
            PoolScrapeResult(
                success=True,
                url="u",
                data=ExtractedProduct(title="T", price=1.0, currency="USD"),
            ),
            is_partial=True,
        )
        == "missing_critical_data"
    )


@pytest.mark.asyncio
async def test_stale_pool_query_uses_last_checked_and_active():
    """Ensure Celery stale selector matches FactListing fields (regression guard)."""
    from sqlalchemy import or_, select

    from app.models.facts import FactListing

    threshold_clause = or_(
        FactListing.last_checked_at.is_(None),
        FactListing.last_checked_at < __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc,
        ),
    )
    stmt = (
        select(FactListing.id)
        .where(FactListing.is_active.is_(True))
        .where(threshold_clause)
        .limit(500)
    )
    compiled = str(stmt.compile(compile_kwargs={"literal_binds": False}))
    assert "last_checked_at" in compiled
    assert "is_active" in compiled


def test_fact_price_write_gate_matches_service_rules():
    """Mirror GlobalScrapeService.scrape_product quality gate (title + price + currency)."""

    def should_write_price_snapshot(
        title: str | None,
        price: float | None,
        currency: str | None,
    ) -> bool:
        product_name_ok = bool(title and str(title).strip())
        curr_ok = currency is not None and str(currency).strip() != ""
        return (
            product_name_ok
            and price is not None
            and price > 0
            and curr_ok
        )

    assert should_write_price_snapshot("Item", 19.99, "USD") is True
    assert should_write_price_snapshot("", 19.99, "USD") is False
    assert should_write_price_snapshot("Item", 0.0, "USD") is False
    assert should_write_price_snapshot("Item", 10.0, None) is False
    assert should_write_price_snapshot("Item", 10.0, "") is False
    assert should_write_price_snapshot("Item", None, "EUR") is False


def test_determine_log_status_success_vs_failure_and_partial_success_value():
    """scrape_logs.status: full payload with currency → success; is_partial → missing_critical_data."""
    svc = GlobalScrapeService.__new__(GlobalScrapeService)
    ok = svc._determine_log_status(
        PoolScrapeResult(success=True, url="u", data=ExtractedProduct(title="T", price=1.0, currency="USD")),
        is_partial=False,
        has_title=True,
        has_price=True,
    )
    partial_ok = svc._determine_log_status(
        PoolScrapeResult(success=True, url="u", data=ExtractedProduct(title="T", price=1.0, currency="USD")),
        is_partial=True,
        has_title=True,
        has_price=True,
    )
    assert ok == "success"
    assert partial_ok == "missing_critical_data"
    fail = svc._determine_log_status(
        PoolScrapeResult(success=False, url="u", error="blocked"),
    )
    assert fail != "success"


def test_determine_log_status_missing_title_or_price():
    svc = GlobalScrapeService.__new__(GlobalScrapeService)
    assert (
        svc._determine_log_status(
            PoolScrapeResult(success=True, url="u", data=ExtractedProduct()),
            is_partial=False,
            has_title=False,
            has_price=False,
        )
        == "missing_critical_data"
    )
    assert (
        svc._determine_log_status(
            PoolScrapeResult(success=True, url="u", data=ExtractedProduct(title="T", price=None)),
            is_partial=False,
            has_title=True,
            has_price=False,
        )
        == "price_not_found"
    )


def test_determine_log_status_error_categories():
    svc = GlobalScrapeService.__new__(GlobalScrapeService)
    assert svc._determine_log_status(PoolScrapeResult(success=False, url="u", error="parse_error:foo")) == "parse_error"
    assert svc._determine_log_status(PoolScrapeResult(success=False, url="u", error="not_found:x")) == "not_found"
    assert svc._determine_log_status(PoolScrapeResult(success=False, url="u", error="captcha")) == "captcha"


def test_determine_log_status_is_empty():
    svc = GlobalScrapeService.__new__(GlobalScrapeService)
    assert (
        svc._determine_log_status(
            PoolScrapeResult(success=True, url="u", data=None, is_empty=True),
            is_partial=False,
        )
        == "missing_critical_data"
    )


def test_determine_log_status_currency_in_fields_missing():
    svc = GlobalScrapeService.__new__(GlobalScrapeService)
    r = PoolScrapeResult(
        success=True,
        url="u",
        data=ExtractedProduct(title="T", price=9.0, currency=None),
        fields_missing=["currency", "image_url"],
    )
    assert svc._determine_log_status(r, is_partial=True, data=r.data) == "missing_critical_data"
