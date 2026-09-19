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


class TestSitemapParity:
    """rust_core::sitemap twins of the enumeration primitives."""

    SITEMAP_INDEX = (
        '<?xml version="1.0"?><sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        "<sitemap><loc>https://s.example/sitemap-1.xml</loc><lastmod>2026-09-01</lastmod></sitemap>"
        "<sitemap><loc>https://s.example/sitemap-2.xml.gz</loc></sitemap></sitemapindex>"
    )
    URLSET = (
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
        'xmlns:xhtml="http://www.w3.org/1999/xhtml">'
        "<url><loc>https://s.example/p/1?x=1&amp;y=2</loc><lastmod>2026-09-18T10:20:30+02:00</lastmod>"
        '<xhtml:link rel="alternate" hreflang="LT" href="https://s.example/lt/p/1"/>'
        '<xhtml:link rel="alternate" hreflang="x-default" href="https://s.example/p/1"></xhtml:link></url>'
        "<url><loc><![CDATA[https://s.example/p/2]]></loc></url>"
        "<url><lastmod>2026-01-01</lastmod></url></urlset>"
    )

    @pytest.mark.parametrize("xml", [SITEMAP_INDEX, URLSET, "<broken", ""])
    def test_parse_sitemap_xml(self, xml, monkeypatch):
        from app.modules.scraper.extractors import parse_sitemap_xml

        monkeypatch.setenv("EXTRACTOR_ENGINE", "python")
        py = parse_sitemap_xml(xml, "https://s.example")
        monkeypatch.setenv("EXTRACTOR_ENGINE", "rust")
        rust = parse_sitemap_xml(xml, "https://s.example")
        assert rust["sitemaps"] == py["sitemaps"]
        assert rust["urls"] == py["urls"]
        assert [e["loc"] for e in rust["url_entries"]] == [e["loc"] for e in py["url_entries"]]
        assert [e["lastmod"] for e in rust["url_entries"]] == [e["lastmod"] for e in py["url_entries"]]
        assert [e["alternates"] for e in rust["url_entries"]] == [e["alternates"] for e in py["url_entries"]]

    @pytest.mark.parametrize(
        "url",
        ["https://S.example/p/1/", "  https://s.example/P/2  ", "https://s.example/", "x"],
    )
    def test_url_hash(self, url, monkeypatch):
        from app.models.facts import FactListing

        monkeypatch.setenv("EXTRACTOR_ENGINE", "python")
        py = FactListing.compute_url_hash(url)
        assert ic.url_hash(url) == py
        assert ic.url_hashes([url, url + "z"]) == [py, FactListing.compute_url_hash(url + "z")]

    @pytest.mark.parametrize(
        "path",
        [
            "/baterii-ansmann-cr2016-1b-5020082", "/catalog/tv/samsung-qe55.html", "/p/12345",
            "/catalog/tv", "/a/b/c", "/detail/1234", "/tovar/abcd", "/x-123.", "/x-12", "/", "",
        ],
    )
    def test_product_like_path(self, path, monkeypatch):
        from app.modules.discovery import sitemap_enumerator as se

        monkeypatch.setenv("EXTRACTOR_ENGINE", "python")
        assert ic.product_like_path(path) == se._url_is_product_like(path), path

    @pytest.mark.parametrize(
        "url",
        [
            "https://shop.example/catalog/laptops", "https://shop.example/c/tv-audio/televizory",
            "https://shop.example/catalog/laptops/lenovo-ideapad-3-1234567", "https://shop.example/product/12345",
            "https://shop.example/login", "https://shop.example/c80196/strana-90098=675621/",
            "https://shop.example/", "https://shop.example/catalog/laptops?page=2",
            "https://shop.example/summer-2024", "https://shop.example/a/b/c/d", "https://shop.example/abcdefghijklmnopq-1",
            "https://shop.example/news/x", "https://shop.example/x.html", "https://shop.example/a/b/1234/",
        ],
    )
    def test_category_like_url(self, url, monkeypatch):
        from app.modules.discovery import sitemap_categories as sc

        monkeypatch.setenv("EXTRACTOR_ENGINE", "python")
        assert ic.category_like_url(url) == sc.category_like(url), url

    LOCALE_URLS = [
        "https://pigu.lt/lt/sitemap-products-5.xml", "https://pigu.lt/RU/x?y=1",
        "https://s.example/en-US/p/1", "https://s.example/p/1", "https://s.example/sitemap.xml",
        "https://s.example", "https://pigu.lt/ru/sitemap-products-images-405.xml",
        "https://s.example/image_sitemap.xml", "https://s.example/sitemaps/video-1.xml",
        "https://s.example/sitemap-imagery.xml", "https://s.example/pt_BR/p/2", "x",
    ]

    @pytest.mark.parametrize("url", LOCALE_URLS)
    def test_url_locale_segment_and_media(self, url, monkeypatch):
        from app.modules.discovery import sitemap_locale as sl

        monkeypatch.setenv("EXTRACTOR_ENGINE", "python")
        assert ic.url_locale_segment(url) == sl.url_locale_segment(url), url
        assert ic.is_media_sitemap(url) == sl.is_media_sitemap(url), url

    @pytest.mark.parametrize(
        ("canonical", "hint", "whole"),
        [
            ("lt", None, True), (None, "RU", True), (None, "et", True), ("xx", None, True),
            ("lt", None, False), ("ru", "lt", False), (None, "ru", False), (None, None, False),
        ],
    )
    def test_select_sitemap_subfiles(self, canonical, hint, whole, monkeypatch):
        from app.modules.discovery import sitemap_locale as sl

        files = [
            "https://pigu.lt/lt/sitemap-products-1.xml",
            "https://pigu.lt/lt/sitemap-products-images-1.xml",
            "https://pigu.lt/ru/sitemap-products-1.xml",
            "https://pigu.lt/ru/sitemap-products-images-1.xml",
            "https://pigu.lt/sitemap-categories.xml",
        ]
        monkeypatch.setenv("EXTRACTOR_ENGINE", "python")
        py = sl.select_sitemap_subfiles(files, canonical, hint, whole)
        rust = ic.select_sitemap_subfiles(files, canonical, hint, whole)
        assert rust["kept"] == py.kept
        assert rust["skipped_media"] == py.skipped_media
        assert rust["skipped_locale"] == py.skipped_locale
        assert rust["locale"] == py.locale

    def test_dominant_locale(self, monkeypatch):
        from app.modules.discovery import sitemap_locale as sl

        pool = ["https://pigu.lt/lt/p/1", "https://pigu.lt/lt/p/2", "https://pigu.lt/lt/p/3",
                "https://pigu.lt/lt/p/4", "https://pigu.lt/ru/p/1"]
        monkeypatch.setenv("EXTRACTOR_ENGINE", "python")
        for share in (0.5, 0.8, 0.9):
            assert ic.dominant_locale(pool, share) == sl.dominant_locale(pool, share)
        assert ic.dominant_locale([], 0.8) == sl.dominant_locale([], 0.8) is None
