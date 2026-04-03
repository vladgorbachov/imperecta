"""Targeted extractors coverage for parse_price, filters, detect_next_page, json-ld."""

from __future__ import annotations

from bs4 import BeautifulSoup

import app.modules.scraper.extractors as ex


def test_parse_price_text_branches():
    assert ex.parse_price_text("1.234.567") is not None
    assert ex.parse_price_text("12,34") is not None
    assert ex.parse_price_text("12,345") is not None
    assert ex.parse_price_text("not-a-number") is None
    assert ex.parse_price_text("0") is None


def test_detect_currency_codes():
    assert ex._detect_currency("price 99 usd") == "USD"
    assert ex._detect_currency("cost 10 eur") == "EUR"
    assert ex._detect_currency("x uah y") == "UAH"
    assert ex._detect_currency("x rub y") == "RUB"
    assert ex._detect_currency("x pln y") == "PLN"
    assert ex._detect_currency("x ron y") == "RON"


def test_merge_results_prefers_first_non_none():
    a = ex.ExtractedProduct(title="A", price=None)
    b = ex.ExtractedProduct(title=None, price=9.0)
    m = ex.merge_results(a, b)
    assert m.title == "A" and m.price == 9.0


def test_extract_auto_detect_meta_price():
    html = """
    <html><head><title>x</title></head><body>
    <meta itemprop="price" content="12.50 USD"/>
    <span class="price current">$15.00</span>
    </body></html>
    """
    soup = BeautifulSoup(html, "html.parser")
    r = ex.extract_auto_detect(soup, "https://shop.example/p")
    assert r.price is not None


def test_extract_product_links_filters():
    html = """
    <html><body>
    <a href="/product/one-12345">a</a>
    <a href="/list/all">bad</a>
    <a href="/category/x">cat</a>
    <a href="/p/ok">ok</a>
    </body></html>
    """
    soup = BeautifulSoup(html, "html.parser")
    urls = ex.extract_product_links(soup, "https://shop.example")
    assert any("/p/ok" in u for u in urls)


def test_extract_product_links_custom_selector():
    html = '<html><body><a class="x" href="/item/99999">x</a></body></html>'
    soup = BeautifulSoup(html, "html.parser")
    urls = ex.extract_product_links(soup, "https://z.com", custom_selector="a.x")
    assert urls


def test_category_and_product_url_helpers():
    assert ex._is_category_url("/shop/catalog/widgets") is True
    assert ex._looks_like_product_url("/dp/1234567890") is True
    assert ex._is_excluded_link("https://x.com/cart") is True


def test_detect_next_page_rel_and_query():
    html = '<html><head><link rel="next" href="/cat?page=2"/></head><body></body></html>'
    soup = BeautifulSoup(html, "html.parser")
    u = ex.detect_next_page(soup, "https://shop.example/cat?page=1")
    assert u and "page=2" in u


def test_extract_product_links_four_segment_path():
    html = """
    <html><body>
    <a href="/seg/one/two/three/four-five">deep</a>
    </body></html>
    """
    soup = BeautifulSoup(html, "html.parser")
    urls = ex.extract_product_links(soup, "https://shop.example")
    assert urls


def test_detect_next_page_russian_label():
    html = """
    <html><body><a href="/page/2">далее</a></body></html>
    """
    soup = BeautifulSoup(html, "html.parser")
    u = ex.detect_next_page(soup, "https://shop.example/list")
    assert u and "page" in u


def test_detect_next_page_increment():
    html = """
    <html><body>
    <a href="/search?page=3">next</a>
    </body></html>
    """
    soup = BeautifulSoup(html, "html.parser")
    u = ex.detect_next_page(soup, "https://shop.example/search?page=2")
    assert u and "page=3" in u


def test_detect_next_page_page_param_sequence():
    html = """
    <html><body>
    <a href="https://shop.example/browse?page=4">more</a>
    </body></html>
    """
    soup = BeautifulSoup(html, "html.parser")
    u = ex.detect_next_page(soup, "https://shop.example/browse?page=3")
    assert u and "page=4" in u




def test_jsonld_graph_product():
    html = """
    <html><head>
    <script type="application/ld+json">
    {"@graph":[{"@type":"Product","name":"G","offers":{"price":"3","priceCurrency":"USD"}}]}
    </script>
    </head><body></body></html>
    """
    soup = BeautifulSoup(html, "html.parser")
    r = ex.extract_from_jsonld(soup)
    assert r.price == 3.0


def test_jsonld_offers_list_and_high_price():
    html = """
    <html><head>
    <script type="application/ld+json">
    {"@type":"Product","name":"P","offers":[{"price":"5","priceCurrency":"EUR"}],
     "image":"https://img.example/i.jpg"}
    </script>
    </head><body></body></html>
    """
    soup = BeautifulSoup(html, "html.parser")
    r = ex.extract_from_jsonld(soup)
    assert r.price == 5.0 and r.image_url


def test_jsonld_offers_as_string():
    html = """
    <html><head>
    <script type="application/ld+json">
    {"@type":"Product","name":"S","offers":"not-a-dict"}
    </script>
    </head><body></body></html>
    """
    soup = BeautifulSoup(html, "html.parser")
    r = ex.extract_from_jsonld(soup)
    assert r.title == "S"


def test_jsonld_high_price_only_branch():
    html = """
    <html><head>
    <script type="application/ld+json">
    {"@type":"Product","name":"H2","offers":{"highPrice":"44","priceCurrency":"GBP"}}
    </script>
    </head><body></body></html>
    """
    soup = BeautifulSoup(html, "html.parser")
    r = ex.extract_from_jsonld(soup)
    assert r.price == 44.0


def test_jsonld_graph_skips_non_dict_nodes():
    html = """
    <html><head>
    <script type="application/ld+json">
    {"@graph":["skip",{"@type":"Product","name":"G2",
      "offers":{"price":"2","priceCurrency":"USD"}}]}
    </script>
    </head><body></body></html>
    """
    soup = BeautifulSoup(html, "html.parser")
    r = ex.extract_from_jsonld(soup)
    assert r.price == 2.0


def test_meta_twitter_data1_price():
    html = """
    <html><head>
    <meta name="twitter:data1" content="29.99"/>
    </head><body></body></html>
    """
    soup = BeautifulSoup(html, "html.parser")
    r = ex.extract_from_meta_tags(soup)
    assert r.price == 29.99


def test_jsonld_type_list_product():
    html = """
    <html><head>
    <script type="application/ld+json">
    {"@type":["Product","Thing"],"name":"L","offers":{"lowPrice":"7","highPrice":"9","priceCurrency":"USD"}}
    </script>
    </head><body></body></html>
    """
    soup = BeautifulSoup(html, "html.parser")
    r = ex.extract_from_jsonld(soup)
    assert r.price == 7.0 and r.original_price == 9.0
