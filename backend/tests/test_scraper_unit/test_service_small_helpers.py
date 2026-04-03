"""Direct tests for module-level helpers in service.py."""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import MagicMock

from app.modules.scraper.service import (
    GlobalScrapeService,
    _optional_in_stock,
    _payload_has_product_name_field,
    _should_replace_placeholder_name,
)
from app.modules.scraper.scraper_pool import PoolScrapeResult


def test_should_replace_placeholder_name_branches():
    assert _should_replace_placeholder_name(None, "https://x") is True
    assert _should_replace_placeholder_name("https://same", "https://same") is True
    assert _should_replace_placeholder_name("999", "https://x") is True
    assert _should_replace_placeholder_name("Real", "https://x") is False


def test_payload_has_product_name_not_dataclass():
    assert _payload_has_product_name_field(object()) is False


def test_optional_in_stock_bool_direct():
    class X:
        in_stock = True

    assert _optional_in_stock(X()) is True


def test_determine_log_status_product_name_field_empty():
    @dataclass
    class P:
        product_name: str
        title: str | None = "T"
        price: float | None = 5.0
        currency: str | None = "USD"

    svc = GlobalScrapeService(MagicMock(), MagicMock())
    p = P(product_name="   ")
    r = PoolScrapeResult(success=True, url="u", data=p)
    assert svc._determine_log_status(r, data=p) == "missing_critical_data"
