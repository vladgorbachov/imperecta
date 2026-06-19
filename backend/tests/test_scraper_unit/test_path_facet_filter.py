"""D2: universal path-facet exclusion in discovery link extraction."""

from __future__ import annotations

import pytest
from bs4 import BeautifulSoup

from app.modules.scraper.extractors import (
    _has_path_facet,
    extract_links_from_repeated_structure,
    extract_product_links,
)


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("/c80196/strana-proizvoditelj-90098=675621/", True),
        ("/igrovie-klaviaturi/c4673273/27726=magnitnye/", True),
        ("/produktai/viskis-jameson-700-ml", False),
        ("/ua/headphones/p366887442/", False),
        ("/c80027/", False),
        ("", False),
        ("/", False),
    ],
)
def test_has_path_facet(path: str, expected: bool) -> None:
    assert _has_path_facet(path) is expected


def test_extract_product_links_excludes_path_facets() -> None:
    base = "https://shop.example"
    html = """
    <a href="/ua/network-adapters/c80196/strana-proizvoditelj-tovara-90098=675621/">facet</a>
    <a href="/ua/igrovie-klaviaturi/c4673273/27726=magnitnye/">facet2</a>
    <a href="/product/headphones-p366887442.html">product</a>
    <a href="/product/viskis-jameson-700-ml-extra-long.html">product2</a>
    """
    soup = BeautifulSoup(html, "html.parser")
    links = extract_product_links(soup, base)
    joined = " ".join(links)
    assert "=" not in joined
    assert "p366887442" in joined
    assert "viskis-jameson" in joined


def test_extract_links_from_repeated_structure_excludes_path_facets() -> None:
    html = """
    <html><body>
      <div class="card"><a href="/ua/network-adapters/c80196/strana-90098=675621/">F1</a></div>
      <div class="card"><a href="/ua/igrovie-klaviaturi/c4673273/27726=magnitnye/">F2</a></div>
      <div class="card"><a href="/product/widget-12345.html">Widget</a></div>
      <div class="card"><a href="/product/widget-12345.html">Widget dup</a></div>
      <div class="card"><a href="/product/guitar-99999.html">Guitar</a></div>
      <div class="card"><a href="/product/guitar-99999.html">Guitar dup</a></div>
      <div class="card"><a href="/product/amp-88888.html">Amp</a></div>
      <div class="card"><a href="/product/amp-88888.html">Amp dup</a></div>
    </body></html>
    """
    soup = BeautifulSoup(html, "html.parser")
    links = extract_links_from_repeated_structure(
        soup,
        "https://shop.example",
        "https://shop.example/catalog",
    )
    joined = " ".join(links)
    assert "=" not in joined
    assert any("widget-12345" in link for link in links)


def test_extract_product_links_keeps_clean_products() -> None:
    base = "https://shop.example"
    html = """
    <a href="/product/alpha-one-12345678.html">A</a>
    <a href="/product/headphones-p366887442.html">B</a>
    <a href="/product/viskis-jameson-700-ml-extra-long.html">C</a>
    """
    soup = BeautifulSoup(html, "html.parser")
    links = extract_product_links(soup, base)
    assert len(links) == 3
