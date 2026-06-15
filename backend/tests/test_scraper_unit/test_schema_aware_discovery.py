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


# ---------------------------------------------------------------------------
# CLASSIFIER-OG-WEBSITE-PRIORITY: a strong structured signal (JSON-LD or
# microdata Product/Listing type) overrides the weak og:type=website
# CMS-default short-circuit. Many shops (bomba.md and similar) emit
# og:type=website on EVERY page; a Product-only override would still leave
# their category pages classified as 'hub' and Phase 2 starved. So Product
# AND Listing must both be recognised under og:type=website. The
# regress-guard test below pins the genuine-hub case.
# ---------------------------------------------------------------------------


def test_layer1_website_with_jsonld_product_returns_product():
    """og:type=website + JSON-LD @type=Product → 'product' (real bomba PDP shape)."""
    pdp = BeautifulSoup(
        '<html><head>'
        '<meta property="og:type" content="website">'
        '<script type="application/ld+json">'
        '{"@type":"Product","name":"X"}'
        '</script>'
        '</head><body></body></html>',
        "html.parser",
    )
    assert (
        classify_page_role_for_discovery(pdp, "https://shop.test/p/1")
        == "product"
    )


def test_layer1_website_with_jsonld_collectionpage_returns_listing():
    """og:type=website + JSON-LD @type=CollectionPage → 'listing'.

    THE category shape that feeds Phase 2 (discovery): without this override,
    bomba-style category pages stay 'hub' → never added to
    discovered_category_urls → Phase 2 has nothing to harvest.
    """
    category = BeautifulSoup(
        '<html><head>'
        '<meta property="og:type" content="website">'
        '<script type="application/ld+json">'
        '{"@type":"CollectionPage","name":"Bass guitars"}'
        '</script>'
        '</head><body></body></html>',
        "html.parser",
    )
    assert (
        classify_page_role_for_discovery(category, "https://shop.test/c/bass")
        == "listing"
    )


def test_layer1_website_with_microdata_product_returns_product():
    """og:type=website + top-level itemtype Product (microdata-only shops)."""
    pdp = BeautifulSoup(
        '<html><head>'
        '<meta property="og:type" content="website">'
        '</head>'
        '<body>'
        '<div itemscope itemtype="https://schema.org/Product">'
        '<span itemprop="name">X</span></div>'
        '</body></html>',
        "html.parser",
    )
    assert (
        classify_page_role_for_discovery(pdp, "https://shop.test/p/1")
        == "product"
    )


def test_layer1_website_with_microdata_collectionpage_returns_listing():
    """og:type=website + top-level itemtype CollectionPage."""
    category = BeautifulSoup(
        '<html><head>'
        '<meta property="og:type" content="website">'
        '</head>'
        '<body>'
        '<div itemscope itemtype="https://schema.org/CollectionPage">'
        '<span itemprop="name">Bass</span></div>'
        '</body></html>',
        "html.parser",
    )
    assert (
        classify_page_role_for_discovery(category, "https://shop.test/c/bass")
        == "listing"
    )


def test_layer1_website_product_wins_over_coexisting_listing():
    """Inside the website branch, Product is checked BEFORE Listing — a PDP
    that ships a coexisting CollectionPage/Breadcrumb must still classify as
    'product' (matching Layer 2's own JSON-LD priority).
    """
    pdp = BeautifulSoup(
        '<html><head>'
        '<meta property="og:type" content="website">'
        '<script type="application/ld+json">'
        '[{"@type":"CollectionPage","name":"X"},{"@type":"Product","name":"Y"}]'
        '</script>'
        '</head><body></body></html>',
        "html.parser",
    )
    assert (
        classify_page_role_for_discovery(pdp, "https://shop.test/p/1")
        == "product"
    )


def test_layer1_website_without_structured_still_hub():
    """REGRESS-GUARD: og:type=website with no stronger structured signal (or
    only hub-typed JSON-LD like WebPage / FAQPage) MUST still return 'hub'.

    The fix is "website yields to a stronger signal", not "website is no
    longer a hub". This test pins universality so no future change accidentally
    drops genuine hubs into 'unknown'/'listing'.
    """
    bare = BeautifulSoup(
        '<html><head>'
        '<meta property="og:type" content="website">'
        '</head><body></body></html>',
        "html.parser",
    )
    assert (
        classify_page_role_for_discovery(bare, "https://shop.test/")
        == "hub"
    )

    webpage = BeautifulSoup(
        '<html><head>'
        '<meta property="og:type" content="website">'
        '<script type="application/ld+json">'
        '{"@type":"WebPage","name":"Home"}'
        '</script>'
        '</head><body></body></html>',
        "html.parser",
    )
    assert (
        classify_page_role_for_discovery(webpage, "https://shop.test/")
        == "hub"
    )
