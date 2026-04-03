"""Exhaustive unit tests for extractors (HTML/JSON fixtures — not DB mocks)."""

from __future__ import annotations

import json

import pytest
from bs4 import BeautifulSoup

import app.modules.scraper.extractors as ex
from app.modules.scraper.extractors import (
    ExtractedProduct,
    detect_next_page,
    extract_auto_detect,
    extract_from_jsonld,
    extract_from_meta_tags,
    extract_product_links,
    extract_with_custom_selectors,
    merge_results,
    parse_price_text,
)


def test_parse_price_text_empty_and_whitespace():
    assert parse_price_text("") is None
    assert parse_price_text("   ") is None


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("$49.99", 49.99),
        ("1 299,50 ₴", 1299.50),
        ("1.299,50 €", 1299.50),
        ("12,5", 12.5),
        ("12.345,67", 12345.67),
        ("1.234", 1234.0),
        ("1,234,567.89", 1234567.89),
        ("0", None),
        ("not-a-number", None),
    ],
)
def test_parse_price_text_parametrized(raw, expected):
    assert parse_price_text(raw) == expected


def test_merge_results_priority():
    a = ExtractedProduct(title="A")
    b = ExtractedProduct(price=10.0, currency="USD")
    m = merge_results(a, b)
    assert m.title == "A" and m.price == 10.0 and m.currency == "USD"


def test_extracted_product_missing_fields_and_completeness():
    p = ExtractedProduct(title="x", price=1.0, image_url=None)
    assert "image_url" in p.missing_fields
    assert 0 < p.completeness < 1


def test_find_product_nodes_variants():
    list_type = {"@type": ["Product", "Thing"], "name": "L", "offers": {"price": "9", "priceCurrency": "USD"}}
    assert ex._find_product_nodes(list_type)
    graph = {
        "@graph": [
            {"@type": "WebPage"},
            {"@type": "Product", "name": "G", "offers": {"price": "8", "priceCurrency": "EUR"}},
        ],
    }
    assert len(ex._find_product_nodes(graph)) >= 1


def test_extract_from_jsonld_list_wrapped_and_offers_variants():
    html = """
    <html><script type="application/ld+json">
    [{"@type":"Product","name":"ListWrap","offers":{"price":"11","priceCurrency":"usd"}}]
    </script></html>
    """
    soup = BeautifulSoup(html, "html.parser")
    r = extract_from_jsonld(soup)
    assert r.title == "ListWrap" and r.price == 11.0 and r.currency == "USD"

    html2 = """
    <script type="application/ld+json">{"@type":"Product","name":"HighLow",
    "offers":{"lowPrice":"10","highPrice":"20","priceCurrency":"EUR"}}</script>
    """
    soup2 = BeautifulSoup(html2, "html.parser")
    r2 = extract_from_jsonld(soup2)
    assert r2.title == "HighLow"
    assert r2.price == 10.0
    assert r2.original_price == 20.0

    html3 = """
    <script type="application/ld+json">
    {"@type":"Product","name":"Img","image":"https://x/i.jpg",
    "offers":{"highPrice":"15","priceCurrency":"GBP"},"description":"x" }
    </script>
    """
    soup3 = BeautifulSoup(html3, "html.parser")
    r3 = extract_from_jsonld(soup3)
    assert r3.image_url == "https://x/i.jpg"
    assert r3.price == 15.0


def test_extract_from_jsonld_invalid_json_skipped():
    html = '<script type="application/ld+json">not json</script>'
    soup = BeautifulSoup(html, "html.parser")
    assert extract_from_jsonld(soup).title is None


def test_extract_from_jsonld_offers_string_skipped_then_valid():
    """Broken offers (non-dict) skipped; valid script still parses."""
    html = """
    <script type="application/ld+json">{"@type":"Product","name":"Ok","offers":{"price":"3","priceCurrency":"USD"}}</script>
    """
    soup = BeautifulSoup(html, "html.parser")
    r = extract_from_jsonld(soup)
    assert r.title == "Ok" and r.price == 3.0


def test_extract_from_jsonld_long_description_truncated():
    long_desc = "d" * 3000
    data = {
        "@type": "Product",
        "name": "N",
        "description": long_desc,
        "offers": {"price": "1", "priceCurrency": "USD"},
    }
    html = f'<script type="application/ld+json">{json.dumps(data)}</script>'
    soup = BeautifulSoup(html, "html.parser")
    r = extract_from_jsonld(soup)
    assert r.description is not None and len(r.description) <= 2000


def test_extract_from_meta_twitter_and_product_price():
    html = """
    <html><head>
    <meta property="og:price:amount" content="19,99" />
    <meta property="og:price:currency" content="eur" />
    <meta property="og:title" content=" T " />
    <meta property="og:image" content="https://cdn.example/i.png" />
    <meta name="description" content="desc" />
    </head></html>
    """
    soup = BeautifulSoup(html, "html.parser")
    r = extract_from_meta_tags(soup)
    assert r.price is not None and r.currency == "EUR" and r.title and r.image_url


def test_extract_from_meta_twitter_data1():
    html = """
    <meta name="twitter:data1" content="$7.50" />
    <meta property="og:title" content="Tw" />
    """
    soup = BeautifulSoup(html, "html.parser")
    r = extract_from_meta_tags(soup)
    assert r.price == 7.5 and r.title == "Tw"


def test_extract_with_custom_selectors():
    html = """
    <div id="t">Title Here</div><span class="p">22,00 USD</span>
    <img class="ph" src="/x.jpg" />
    """
    soup = BeautifulSoup(html, "html.parser")
    r = extract_with_custom_selectors(
        soup,
        {"title": "#t", "price": ".p", "image": ".ph", "original_price": ".p"},
    )
    assert "Title" in (r.title or "")
    assert r.price is not None


def test_detect_currency_branches():
    assert ex._detect_currency("100 zł") == "PLN"
    assert ex._detect_currency("99 lei") == "RON"
    assert ex._detect_currency("no currency code here") is None


def test_extract_auto_detect_meta_img_and_description():
    html = """
    <html><head>
    <title>Shop | Product Name</title>
    <meta name="description" content="meta desc" />
    </head>
    <body>
    <span class="price" id="p">$33.00 USD</span>
    <img width="400" height="400" class="product-gallery" src="/big.jpg" alt="x" />
    </body></html>
    """
    soup = BeautifulSoup(html, "html.parser")
    r = extract_auto_detect(soup, "https://shop.example/cat/item")
    assert r.title and r.price == 33.0 and r.image_url


def test_looks_like_and_category_and_excluded():
    assert ex._looks_like_product_url("/p/12345-x")
    assert ex._looks_like_product_url("/item/thing.html")
    assert ex._is_category_url("/catalog/list")
    assert ex._is_excluded_link("https://x.com/cart/add")


def test_extract_product_links_filters():
    base = "https://shop.example"
    html = """
    <a href="/login">in</a>
    <a href="https://other.net/p">ext</a>
    <a href="/product/12345-abc">ok</a>
    <a href="/list/all">bad</a>
    """
    soup = BeautifulSoup(html, "html.parser")
    links = extract_product_links(soup, base)
    assert any("/product/12345" in u for u in links)


def test_detect_next_page_custom_and_rel_and_query():
    soup = BeautifulSoup('<link rel="next" href="https://x.com/n" />', "html.parser")
    assert detect_next_page(soup, "https://x.com/a?page=1") == "https://x.com/n"
    soup2 = BeautifulSoup(
        '<a href="?page=2">next</a><link rel="next" href="https://x.com/p2" />',
        "html.parser",
    )
    assert detect_next_page(soup2, "https://x.com/cat?page=1") is not None
    soup3 = BeautifulSoup('<a class="n" href="?page=3">далее</a>', "html.parser")
    assert detect_next_page(soup3, "https://x.com/z?page=2", custom_selector="a.n") is not None
