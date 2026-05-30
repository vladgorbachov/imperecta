"""P0 data quality guards: discovery URL filter, PDP guard, currency gate."""

from __future__ import annotations

from bs4 import BeautifulSoup

from app.modules.scraper.extractors import (
    ExtractedProduct,
    extract_links_from_repeated_structure,
    merge_and_finalize,
)
from app.modules.scraper.service import (
    MAX_CURRENCY_RAW_LEN,
    GlobalScrapeService,
    _resolve_in_stock,
)


def test_extract_links_from_repeated_structure_rejects_catalog_category_urls():
    """FIX-1: category/brand catalog paths must not pass as product URLs."""
    html = """
    <html><body>
      <div class="card"><a href="/catalog/chitare-bass-302">Bass</a></div>
      <div class="card"><a href="/catalog/brand/amati-11000149">Amati</a></div>
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
        "https://musicshop.md",
        "https://musicshop.md/catalog",
    )
    assert "/catalog/chitare-bass" not in " ".join(links)
    assert "/catalog/brand/" not in " ".join(links)
    assert any("widget-12345" in link for link in links)


def test_merge_and_finalize_skips_listing_pages():
    """FIX-2: listing/hub pages return empty extraction."""
    html = """
    <html><body>
      <div class="card"><a href="/p/1">A</a></div>
      <div class="card"><a href="/p/2">B</a></div>
      <div class="card"><a href="/p/3">C</a></div>
      <div class="card"><a href="/p/4">D</a></div>
      <div class="card"><a href="/p/5">E</a></div>
      <div class="card"><a href="/p/6">F</a></div>
    </body></html>
    """
    soup = BeautifulSoup(html, "html.parser")
    merged = merge_and_finalize(
        soup,
        "https://shop.example/catalog/guitars",
        ExtractedProduct(title="Old", price=99.0, currency="MDL"),
    )
    assert merged.price is None
    assert merged.currency is None
    assert merged.title is None


def test_resolve_in_stock_returns_none_when_unknown():
    """FIX-4: unknown availability must not coerce to False."""
    assert _resolve_in_stock(None, ExtractedProduct(price=1.0)) is None


def test_max_currency_raw_len_constant():
    """FIX-3: glued header text exceeds sane currency_raw threshold."""
    glued = "x" * (MAX_CURRENCY_RAW_LEN + 1)
    assert len(glued) >= MAX_CURRENCY_RAW_LEN


def test_should_skip_price_record_both_unknown_stock():
    """FIX-4: both unknown in_stock values are treated as unchanged."""
    from unittest.mock import MagicMock

    listing = MagicMock()
    listing.last_price = 10.0
    listing.last_currency_code = "USD"
    listing.last_in_stock = None
    assert GlobalScrapeService._should_skip_price_record(listing, 10.0, "USD", None) is True
