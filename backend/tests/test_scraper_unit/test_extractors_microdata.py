"""HTML5 Microdata structural extraction (schema.org/Product via itemprop).

Pins the new ``extract_from_microdata`` strategy: top-level Product only,
nested Offer descent, W3C value rule (meta→content / a→href / img→src /
else→text), gate-clean ``currency_raw`` (short, never glued body text), and
the chain integration that prevents microdata-only pages from falling to the
body-text fallback. Universal — keys only off DOM + schema.org vocabulary.
"""

from __future__ import annotations

from bs4 import BeautifulSoup

from app.modules.scraper.extractors import (
    ExtractedProduct,
    extract_from_jsonld,
    extract_from_meta_tags,
    extract_from_microdata,
    merge_and_finalize,
)


# Mirror of gate constant; the whole point of this strategy is to keep
# currency_raw short. Hard-coded here so this test file is self-contained.
_MAX_CURRENCY_RAW_LEN = 50


def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


def test_extract_from_microdata_product_offer():
    """Top-level Product with a nested Offer — the typical microdata-only PDP."""
    html = """
    <html><body>
      <div itemscope itemtype="http://schema.org/Product">
        <h1 itemprop="name">Bosch Kuhlschrank</h1>
        <img itemprop="image" src="/img/p.jpg"/>
        <div itemscope itemtype="http://schema.org/Offer">
          <span itemprop="price">599,99</span>
          <meta itemprop="priceCurrency" content="EUR"/>
        </div>
      </div>
    </body></html>
    """
    r = extract_from_microdata(_soup(html), "https://shop.example/p/1")

    assert r.title == "Bosch Kuhlschrank"
    assert r.price == 599.99
    assert r.currency == "EUR"
    assert r.currency_raw == "EUR"
    assert len(r.currency_raw) < _MAX_CURRENCY_RAW_LEN
    assert r.image_url == "https://shop.example/img/p.jpg"


def test_extract_from_microdata_price_in_product_scope_no_offer():
    """price/priceCurrency directly on the Product (no nested Offer) — works."""
    html = """
    <html><body>
      <article itemscope itemtype="https://schema.org/Product">
        <h1 itemprop="name">Direct Product</h1>
        <span itemprop="price">12.50</span>
        <meta itemprop="priceCurrency" content="USD"/>
      </article>
    </body></html>
    """
    r = extract_from_microdata(_soup(html), "https://shop.example/p/2")

    assert r.title == "Direct Product"
    assert r.price == 12.50
    assert r.currency == "USD"
    assert r.currency_raw == "USD"


def test_extract_from_microdata_meta_content_value_rule():
    """W3C content-attr value rule: <meta itemprop="..."> reads `content`."""
    html = """
    <html><body>
      <div itemscope itemtype="http://schema.org/Product">
        <meta itemprop="name" content="Meta-Only Item"/>
        <div itemscope itemtype="http://schema.org/Offer">
          <meta itemprop="price" content="12.99"/>
          <meta itemprop="priceCurrency" content="USD"/>
        </div>
      </div>
    </body></html>
    """
    r = extract_from_microdata(_soup(html), "https://shop.example/p/3")

    assert r.title == "Meta-Only Item"
    assert r.price == 12.99
    assert r.currency == "USD"


def test_extract_from_microdata_currency_symbol_fallback():
    """No priceCurrency → currency detected from glued symbol, currency_raw short."""
    html = """
    <html><body>
      <div itemscope itemtype="http://schema.org/Product">
        <h1 itemprop="name">Symbol-Currency Item</h1>
        <span itemprop="price">12,99 \u20ac</span>
      </div>
    </body></html>
    """
    r = extract_from_microdata(_soup(html), "https://shop.example/p/4")

    assert r.price == 12.99
    assert r.currency == "EUR"
    # Crucially — short, gate-clean, NOT 100 chars of body text.
    assert r.currency_raw is not None
    assert len(r.currency_raw) < _MAX_CURRENCY_RAW_LEN


def test_extract_from_microdata_nested_product_card_ignored():
    """Category page: Product card nested inside ItemList → no top-level Product
    → empty result (price/currency None). Pins the top-level-only contract.
    """
    html = """
    <html><body>
      <div itemscope itemtype="http://schema.org/ItemList">
        <div itemscope itemtype="http://schema.org/Product">
          <h1 itemprop="name">Card Title</h1>
          <span itemprop="price">9.99</span>
          <meta itemprop="priceCurrency" content="EUR"/>
        </div>
      </div>
    </body></html>
    """
    r = extract_from_microdata(_soup(html), "https://shop.example/cat")

    assert r.price is None
    assert r.currency is None
    assert r.currency_raw is None


def test_extract_from_microdata_non_microdata_page_empty():
    """Plain HTML, no itemscope/itemtype → empty ExtractedProduct, no raise."""
    html = "<html><body><h1>Not a microdata page</h1><p>just text</p></body></html>"
    r = extract_from_microdata(_soup(html), "https://shop.example/p/x")

    assert r.price is None
    assert r.currency is None
    assert r.currency_raw is None


def test_microdata_short_circuits_body_text_fallback_via_merge():
    """End-to-end chain: a microdata-only page (no JSON-LD, no OG) routed
    through merge_and_finalize yields gate-clean currency_raw="EUR" — not the
    glued body-text fallback that the bug produced.
    """
    html = """
    <html><body>
      <div itemscope itemtype="http://schema.org/Product">
        <h1 itemprop="name">Microdata Product</h1>
        <img itemprop="image" src="https://shop.example/img/p.jpg"/>
        <div itemscope itemtype="http://schema.org/Offer">
          <span itemprop="price">25,00</span>
          <meta itemprop="priceCurrency" content="EUR"/>
        </div>
      </div>
    </body></html>
    """
    soup = _soup(html)
    url = "https://shop.example/p/integration"

    jsonld = extract_from_jsonld(soup, url)
    microdata = extract_from_microdata(soup, url)
    meta = extract_from_meta_tags(soup, url)
    custom = ExtractedProduct()

    # Skip extract_auto_detect at this layer — the contract being pinned is
    # that microdata wins over downstream strategies for currency_raw, so an
    # empty auto positional is sufficient. (auto would also produce a clean
    # output here; the test stays decoupled from auto-detect heuristics.)
    auto = ExtractedProduct()

    out = merge_and_finalize(soup, url, jsonld, microdata, meta, custom, auto)

    assert out.title == "Microdata Product"
    assert out.price == 25.00
    assert out.currency == "EUR"
    assert out.currency_raw == "EUR"
    assert len(out.currency_raw) < _MAX_CURRENCY_RAW_LEN
