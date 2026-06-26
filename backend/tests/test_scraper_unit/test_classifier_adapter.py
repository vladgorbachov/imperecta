"""Pure-logic tests for discovery classifier_adapter (no DB/network)."""

from __future__ import annotations

from bs4 import BeautifulSoup

from app.modules.classifier import classify_page_role_for_discovery
from app.modules.discovery import classifier_adapter


def test_classify_page_role_delegates_to_underlying_function() -> None:
    soup = BeautifulSoup(
        '<html><head><meta property="og:type" content="product"></head><body></body></html>',
        "html.parser",
    )
    base_url = "https://shop.example/p/1"

    assert classifier_adapter.classify_page_role(soup, base_url) == (
        classify_page_role_for_discovery(soup, base_url)
    )
    assert classifier_adapter.classify_page_role(soup, base_url) == "product"


def test_classify_page_role_product_via_og_matches_direct() -> None:
    soup = BeautifulSoup(
        '<html><head><meta property="og:type" content="product"></head><body></body></html>',
        "html.parser",
    )
    url = "https://x.test/p/1"
    assert classifier_adapter.classify_page_role(soup, url) == "product"
    assert classifier_adapter.classify_page_role(soup, url) == (
        classify_page_role_for_discovery(soup, url)
    )


def test_classify_page_role_hub_via_og_website_matches_direct() -> None:
    soup = BeautifulSoup(
        '<html><head><meta property="og:type" content="website"></head><body></body></html>',
        "html.parser",
    )
    url = "https://x.test/"
    assert classifier_adapter.classify_page_role(soup, url) == "hub"
    assert classifier_adapter.classify_page_role(soup, url) == (
        classify_page_role_for_discovery(soup, url)
    )


def test_classify_page_role_listing_via_jsonld_matches_direct() -> None:
    soup = BeautifulSoup(
        '<html><head><script type="application/ld+json">'
        '{"@type":"CollectionPage","name":"Bass"}'
        '</script></head><body></body></html>',
        "html.parser",
    )
    url = "https://shop.test/c/bass"
    assert classifier_adapter.classify_page_role(soup, url) == "listing"
    assert classifier_adapter.classify_page_role(soup, url) == (
        classify_page_role_for_discovery(soup, url)
    )
