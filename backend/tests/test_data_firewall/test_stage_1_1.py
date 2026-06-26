"""data_firewall stage 1.1 — behavior-preserving gate absorption tests."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

import pytest

from app.modules.data_firewall.contracts import FACT_TABLE_CONTRACTS
from app.modules.data_firewall.firewall import evaluate_ecommerce, evaluate_market
from app.modules.data_firewall.rules import MAX_CURRENCY_RAW_LEN
from app.modules.ingestion.gate import (
    SKIP_CURRENCY_COUNTRY_MISMATCH,
    SKIP_CURRENCY_RAW_TOO_LONG,
    SKIP_MISSING_NAME_OR_CURRENCY,
    SKIP_PRICE_NOT_POSITIVE,
    evaluate_gate,
)
from app.modules.scraper.extractors import ExtractedProduct, merge_and_finalize
from bs4 import BeautifulSoup


class _FakeResolver:
    def __init__(self, allowed: frozenset[str]) -> None:
        self._allowed = allowed

    def matches(self, marketplace_id, currency: str | None) -> bool:  # noqa: ANN001
        return bool(currency and currency.upper() in self._allowed)


@dataclass
class _FakeData:
    product_name: str | None = "Widget"
    title: str | None = "Widget"
    price: float | None = 19.0
    currency: str | None = "EUR"
    currency_raw: str | None = "19.0 EUR"
    page_role: str | None = None


def _assert_same_decision(legacy, fw) -> None:  # noqa: ANN001
    assert legacy.passed == fw.passed
    assert legacy.skip_reason == fw.reject_reason
    assert legacy.forced_log_status == fw.forced_log_status


@pytest.mark.parametrize(
    "data",
    [
        _FakeData(),
        _FakeData(price=0.0),
        _FakeData(currency=None, currency_raw=None),
        _FakeData(
            currency="EUR",
            currency_raw="EUR " + "x" * MAX_CURRENCY_RAW_LEN,
        ),
        _FakeData(currency="SEK", currency_raw="19.0 SEK"),
        _FakeData(product_name=None, title=None),
    ],
)
def test_data_firewall_matches_legacy_gate(data: _FakeData) -> None:
    mp_id = uuid4()
    resolver = _FakeResolver(frozenset({"EUR"}))
    legacy = evaluate_gate(data, marketplace_id=mp_id, currency_resolver=resolver)
    fw = evaluate_ecommerce(
        data,
        marketplace_id=mp_id,
        currency_resolver=resolver,
        page_role=data.page_role,
    )
    _assert_same_decision(legacy, fw)


def test_data_firewall_matches_legacy_gate_country_mismatch_reason() -> None:
    mp_id = uuid4()
    data = _FakeData(currency="SEK", currency_raw="19.0 SEK")
    resolver = _FakeResolver(frozenset({"EUR"}))
    fw = evaluate_ecommerce(data, marketplace_id=mp_id, currency_resolver=resolver)
    assert not fw.passed
    assert fw.reject_reason == SKIP_CURRENCY_COUNTRY_MISMATCH
    assert fw.forced_log_status == "currency_rejected"


def test_page_role_listing_blocked_in_stage_1_2() -> None:
    mp_id = uuid4()
    data = _FakeData(page_role="listing")
    resolver = _FakeResolver(frozenset({"EUR"}))
    fw_listing = evaluate_ecommerce(
        data,
        marketplace_id=mp_id,
        currency_resolver=resolver,
        page_role="listing",
    )
    assert not fw_listing.passed
    assert fw_listing.page_role_verdict == "non_product"
    assert fw_listing.reject_reason == "not_a_product"


def test_page_role_on_extracted_product_from_classifier() -> None:
    html = """
    <html><head>
    <meta property="og:type" content="product"/>
    <script type="application/ld+json">
    {"@type":"Product","name":"Widget","offers":{"price":"10","priceCurrency":"EUR"}}
    </script>
    </head><body><h1>Widget</h1></body></html>
    """
    soup = BeautifulSoup(html, "html.parser")
    merged = merge_and_finalize(soup, "https://shop.example/p/1", ExtractedProduct())
    assert merged.page_role == "product"


def test_contract_structure_loaded() -> None:
    assert len(FACT_TABLE_CONTRACTS) == 16
    assert "dim_date" in FACT_TABLE_CONTRACTS
    assert "scrape_jobs" in FACT_TABLE_CONTRACTS
    assert "dim_marketplace" in FACT_TABLE_CONTRACTS
    assert "fact_price" in FACT_TABLE_CONTRACTS
    assert "fact_stock" not in FACT_TABLE_CONTRACTS
    assert "in_stock" not in FACT_TABLE_CONTRACTS["fact_price"]
    price_contract = FACT_TABLE_CONTRACTS["fact_price"]["price"]
    assert price_contract["type"] == "numeric"
    assert price_contract["nullable"] is False
    assert price_contract["precision"] == 12
    assert price_contract["scale"] == 2
    search_source = FACT_TABLE_CONTRACTS["fact_search_trend"]["source"]
    assert search_source.get("check_values") is not None


def test_market_rail_wired_in_stage_1_2() -> None:
    from app.modules.market_data import ingestion as market_ingestion

    source = open(market_ingestion.__file__, encoding="utf-8").read()
    assert "evaluate_market" in source
    assert "write_sync" in source
