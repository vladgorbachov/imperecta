"""D1-A+C: AUTO extraction quality and honest currency-rejected gate status."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from bs4 import BeautifulSoup

from app.common import html_parsing as hp
from app.modules.ingestion.gate import (
    SKIP_CURRENCY_COUNTRY_MISMATCH,
    SKIP_CURRENCY_RAW_TOO_LONG,
    evaluate_gate,
)
from app.modules.ingestion.gate import MAX_CURRENCY_RAW_LEN
from app.modules.scraper.extractors import (
    _detect_currency,
    extract_auto_detect,
    extract_from_jsonld,
    extract_from_meta_tags,
    extract_from_microdata,
    merge_and_finalize,
)


def test_auto_ignores_verification_meta():
    html = """
    <html><head>
    <meta name="facebook-domain-verification"
          content="19ljatf5u9i2dlkrt4sqjawoeo8qdb" />
    <title>Product</title>
    </head><body><h1>Milk</h1></body></html>
    """
    soup = BeautifulSoup(html, "html.parser")
    result = extract_auto_detect(soup, "https://shop.example/p/1")
    assert result.price is None
    assert result.currency is None


def test_auto_rejects_date_as_price():
    assert hp.parse_price_text("Kaina galioja iki 2026-06-29") is None
    assert hp.parse_price_text("2026 EUR") == 2026.0


def test_detect_currency_token_boundary():
    assert _detect_currency("19ljatf5u9i2dlkrt4sqjawoeo8qdb") is None
    assert _detect_currency("49.99 kr") == "SEK"
    assert _detect_currency("12,99 €") == "EUR"


def test_auto_keeps_contextual_price():
    html = """
    <html><head><title>Widget</title></head>
    <body><span class="price">49.99 €</span></body></html>
    """
    soup = BeautifulSoup(html, "html.parser")
    result = extract_auto_detect(soup, "https://shop.example/p/1")
    assert result.price == 49.99
    assert result.currency == "EUR"


class _FakeResolver:
    """In-memory CurrencyResolver substitute (no DB calls)."""

    def __init__(self, allowed: frozenset[str]) -> None:
        self._allowed = allowed

    def matches(self, marketplace_id, currency: str | None) -> bool:  # noqa: ANN001
        return bool(currency and currency.upper() in self._allowed)


@dataclass
class _FakeData:
    product_name: str | None = "Widget"
    title: str | None = "Widget"
    price: float | None = 19.0
    currency: str | None = "SEK"
    currency_raw: str | None = "19.0 SEK"


def test_gate_currency_rejection_status_mismatch():
    outcome = evaluate_gate(
        _FakeData(currency="SEK"),
        marketplace_id=uuid4(),
        currency_resolver=_FakeResolver(frozenset({"EUR"})),
    )
    assert not outcome.passed
    assert outcome.skip_reason == SKIP_CURRENCY_COUNTRY_MISMATCH
    assert outcome.forced_log_status == "currency_rejected"
    assert outcome.forced_log_status != "parse_error"


def test_gate_currency_rejection_status_raw_too_long():
    glued = "EUR " + "x" * MAX_CURRENCY_RAW_LEN
    outcome = evaluate_gate(
        _FakeData(currency="EUR", currency_raw=glued),
        marketplace_id=uuid4(),
        currency_resolver=_FakeResolver(frozenset({"EUR"})),
    )
    assert not outcome.passed
    assert outcome.skip_reason == SKIP_CURRENCY_RAW_TOO_LONG
    assert outcome.forced_log_status == "currency_rejected"


def test_barbora_like_yields_no_garbage():
    html = """
    <html><head>
    <meta name="facebook-domain-verification"
          content="19ljatf5u9i2dlkrt4sqjawoeo8qdb" />
    <title>Barbora product</title>
    </head><body>
    <h1>Organic milk</h1>
    <p>Kaina galioja iki 2026-06-29</p>
    </body></html>
    """
    soup = BeautifulSoup(html, "html.parser")
    url = "https://barbora.lt/produktai/milk-1"
    merged = merge_and_finalize(
        soup,
        url,
        extract_from_jsonld(soup, url),
        extract_from_microdata(soup, url),
        extract_from_meta_tags(soup, url),
        extract_auto_detect(soup, url),
    )
    assert merged.price is None
    assert merged.currency is None
