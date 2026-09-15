"""Parity harness: Rust extraction core vs the Python reference.

Skipped automatically when the compiled module is absent (CI has no Rust
toolchain yet); locally run after `maturin develop --release` in
backend/rust_core. The flag flip (EXTRACTOR_ENGINE=rust) is blessed only
while this file is green.
"""

from __future__ import annotations

import json

import pytest
from bs4 import BeautifulSoup

ic = pytest.importorskip("imperecta_core")

from app.common import html_parsing as hp  # noqa: E402
from app.modules.scraper.extractors import extract_from_jsonld  # noqa: E402

PRICE_CORPUS = [
    "1,234.56",
    "1.234,56",
    "1 234,56",
    "1 234.56",
    "1234,56",
    "1234.56",
    "1234",
    "19,99 €",
    "Цена: 1 299,50 грн",
    "старая цена 2 500 руб, скидка 20%",
    "1 299,00 zł",
    "od 49,90 zł",
    "£10.50",
    "$1,099",
    "55 lei",
    "199 kr.",
    "5 990 Ft",
    "copyright 2024",
    "2026-01-15",
    "2024 €",
    "выпущен в 2021 году",
    "cashback 500",
    "бонус 300, цена 4 500 тг",
    "1.299 лв",
    "9 999 999",
    "9 999 999 €",
    "0,99 €",
    "",
    "no numbers at all",
    "12.345.678",
    "1.2.3",
    "SKU 12345, price 129.99 USD",
    "3 items for 10,00",
]

CURRENCY_CORPUS = [
    "19,99 €",
    "$5",
    "£3",
    "100 uah",
    "100 грн",
    "55 лей",
    "55 lei",
    "199 kr",
    "kr199",
    "digikr8",
    "10 zł",
    "5 990 ft",
    "120 руб",
    "тенге 5000",
    "IDR 5000",
    "price: 12 CHF",
    "",
    "просто текст",
    "бел.руб 25",
    "12 man",
]

JSONLD_FIXTURES = [
    # Product at top level, string price with EU format
    """<html><head><script type="application/ld+json">
    {"@context":"https://schema.org","@type":"Product","name":"Дрель Bosch",
     "brand":"Bosch","image":{"url":"https://s.example/i.jpg"},
     "description":"Хорошая дрель",
     "offers":{"@type":"Offer","price":"1 299,50","priceCurrency":"ron"}}
    </script></head><body><h1>fallback</h1></body></html>""",
    # @graph with Product + BreadcrumbList; category from breadcrumbs
    """<html><head><title>Widget X | Shop</title>
    <script type="application/ld+json">
    {"@context":"https://schema.org","@graph":[
      {"@type":["Product"],"name":"Widget X","brand":{"name":"Acme"},
       "image":["https://s.example/1.jpg","https://s.example/2.jpg"],
       "offers":[{"@type":"Offer","price":149.0,"priceCurrency":"EUR"}]},
      {"@type":"BreadcrumbList","itemListElement":[
        {"@type":"ListItem","position":1,"name":"Home","item":"https://shop.example/"},
        {"@type":"ListItem","position":2,"name":"Tools","item":{"@id":"https://shop.example/tools","name":"Tools"}},
        {"@type":"ListItem","position":3,"name":"Widget X","item":"https://shop.example/tools/widget-x"}]}
    ]}</script></head><body></body></html>""",
    # AggregateOffer low/high, category as string path
    """<html><head><script type="application/ld+json">
    [{"@type":"Product","name":"Y","category":"Home > Garden > Hoses",
      "offers":{"@type":"AggregateOffer","lowPrice":"100","highPrice":"150","priceCurrency":"USD"}}]
    </script></head><body></body></html>""",
    # Broken JSON first, valid product second script
    """<html><head>
    <script type="application/ld+json">{not json</script>
    <script type="application/ld+json">{"@type":"product","name":"lower-type",
      "offers":{"price":"49.90","priceCurrency":"eur"}}</script>
    </head><body></body></html>""",
    # No product at all -> title fallback path
    """<html><head><title>Just a page — Site</title>
    <script type="application/ld+json">{"@type":"WebSite","name":"Site"}</script>
    </head><body></body></html>""",
    # Offers as plain string (tolerated), image list empty
    """<html><head><script type="application/ld+json">
    {"@type":"Product","name":"Z","offers":"broken","image":[]}
    </script></head><body></body></html>""",
]

PAGE_URL = "https://shop.example/tools/widget-x"


class TestPricingParity:
    @pytest.mark.parametrize("text", PRICE_CORPUS)
    def test_parse_price_text(self, text, monkeypatch):
        monkeypatch.setenv("EXTRACTOR_ENGINE", "python")
        expected = hp.parse_price_text(text)
        got = ic.parse_price_text(text)
        assert got == pytest.approx(expected) if expected is not None else got is None, (
            f"{text!r}: python={expected} rust={got}"
        )

    @pytest.mark.parametrize("text", CURRENCY_CORPUS)
    def test_currency_detection(self, text, monkeypatch):
        monkeypatch.setenv("EXTRACTOR_ENGINE", "python")
        assert ic.parse_currency_symbol(text) == hp.parse_currency_symbol(text), text
        assert ic.parse_currency_code(text) == hp.parse_currency_code(text), text
        assert ic.detect_currency(text) == hp._detect_currency(text), text

    @pytest.mark.parametrize(
        "raw", ["55 lei", "лей", "kr", "kr.", "KR", "€", "", None, "some kroner"]
    )
    def test_ambiguity_parity(self, raw):
        assert ic.currency_token_is_ambiguous(raw) == hp.currency_token_is_ambiguous(raw)


class TestJsonLdParity:
    @pytest.mark.parametrize("html", JSONLD_FIXTURES)
    def test_extract_matches_python(self, html, monkeypatch):
        soup = BeautifulSoup(html, "html.parser")

        monkeypatch.setenv("EXTRACTOR_ENGINE", "python")
        py = extract_from_jsonld(soup, PAGE_URL)

        monkeypatch.setenv("EXTRACTOR_ENGINE", "rust")
        rust = extract_from_jsonld(soup, PAGE_URL)

        for field in (
            "title",
            "price",
            "original_price",
            "currency",
            "image_url",
            "description",
            "price_raw_text",
            "currency_raw",
            "brand",
            "category_path",
        ):
            assert getattr(rust, field) == getattr(py, field), (
                f"field {field}: python={getattr(py, field)!r} rust={getattr(rust, field)!r}"
            )


class TestEngineFlag:
    def test_default_is_python(self, monkeypatch):
        monkeypatch.delenv("EXTRACTOR_ENGINE", raising=False)
        assert hp._use_rust() is False

    def test_rust_flag_enables(self, monkeypatch):
        monkeypatch.setenv("EXTRACTOR_ENGINE", "rust")
        assert hp._use_rust() is True

    def test_unknown_value_stays_python(self, monkeypatch):
        monkeypatch.setenv("EXTRACTOR_ENGINE", "warp-drive")
        assert hp._use_rust() is False


class TestQualityModule:
    def test_full_record_scores_a(self):
        report = ic.assess_quality(
            {
                "title": "Bosch GSR 12V-30",
                "price": 129.99,
                "original_price": 149.99,
                "currency": "EUR",
                "currency_raw": "€",
                "image_url": "https://s.example/i.jpg",
                "url": "https://shop.example/p/1",
                "description": "drill",
                "brand": "Bosch",
                "category_path": ["Tools"],
                "allowed_currencies": ["EUR"],
            }
        )
        assert report["score"] == 100 and report["grade"] == "A"
        assert report["critical"] is False

    def test_currency_whitelist_violation_critical(self):
        report = ic.assess_quality(
            {"title": "X", "price": 5.0, "currency": "RUB", "allowed_currencies": ["MDL"]}
        )
        assert report["critical"] is True
        assert "currency_not_allowed" in report["flags"]

    def test_json_serializable(self):
        report = ic.assess_quality({"title": None, "price": None})
        json.dumps(report)  # flags list + scalars only
        assert report["critical"] is True  # missing title + price? title critical
