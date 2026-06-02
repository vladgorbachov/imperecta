"""Schema-aware discovery classifier and _is_category_url slug fix."""

from __future__ import annotations

from bs4 import BeautifulSoup

from app.modules.scraper.extractors import (
    _is_category_url,
    classify_page_role_for_discovery,
)


def test_classify_page_role_for_discovery_og_product():
    pdp = BeautifulSoup(
        '<html><head><meta property="og:type" content="product"></head><body></body></html>',
        "html.parser",
    )
    assert classify_page_role_for_discovery(pdp, "https://x.test/p/1") == "product"


def test_classify_page_role_for_discovery_og_website_hub():
    hub = BeautifulSoup(
        '<html><head><meta property="og:type" content="website"></head><body></body></html>',
        "html.parser",
    )
    assert classify_page_role_for_discovery(hub, "https://x.test/") == "hub"


def test_classify_page_role_for_discovery_og_article_listing():
    blog = BeautifulSoup(
        '<html><head><meta property="og:type" content="article"></head><body></body></html>',
        "html.parser",
    )
    assert classify_page_role_for_discovery(blog, "https://x.test/blog/1") == "listing"


def test_classify_page_role_for_discovery_jsonld_product():
    ld_pdp = BeautifulSoup(
        '<html><head><script type="application/ld+json">{"@type":"Product","name":"x"}'
        '</script></head><body></body></html>',
        "html.parser",
    )
    assert classify_page_role_for_discovery(ld_pdp, "https://x.test/p/1") == "product"


def test_classify_page_role_for_discovery_jsonld_product_wins_breadcrumb():
    ld_pdp = BeautifulSoup(
        '<html><head><script type="application/ld+json">'
        '[{"@type":"Product","name":"x"},{"@type":"BreadcrumbList"}]'
        '</script></head><body></body></html>',
        "html.parser",
    )
    assert classify_page_role_for_discovery(ld_pdp, "https://x.test/p/1") == "product"


def test_classify_page_role_for_discovery_plain_fallback():
    plain = BeautifulSoup("<html><body></body></html>", "html.parser")
    result = classify_page_role_for_discovery(plain, "https://x.test/p/1")
    assert result in ("product", "listing", "hub", "unknown")


def test_is_category_url_catalog_root():
    assert _is_category_url("/catalog") is True


def test_is_category_url_subcategory_short_id():
    assert _is_category_url("/catalog/chitare-bass-302") is True


def test_is_category_url_pdp_under_catalog():
    assert _is_category_url("/catalog/electronics/iphone-15-12345678") is False
    assert _is_category_url("/catalog/brand/some-product-11000149") is False


def test_is_category_url_sale_year_suffix():
    assert _is_category_url("/sale/summer-2024") is True


def test_is_category_url_short_numeric_category():
    assert _is_category_url("/notebooks/c80004/") is False


def test_is_category_url_standalone_numeric_pdp():
    assert _is_category_url("/p/12345678") is False


def test_is_category_url_html_pdp():
    assert _is_category_url("/laptop-name.html") is False
