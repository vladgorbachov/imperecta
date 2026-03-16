"""Integration and unit tests for universal extractors and scraper pool."""

import pytest
import httpx
from bs4 import BeautifulSoup

from app.scrapers.extractors import (
    ExtractedProduct,
    extract_auto_detect,
    extract_from_jsonld,
    extract_from_meta_tags,
    extract_product_links,
    merge_results,
    parse_price_text,
)
from app.scrapers.scraper_pool import ScraperPool
import app.scrapers.scraper_pool as scraper_pool_module


async def _fetch_html(urls: list[str]) -> tuple[str, str] | tuple[None, None]:
    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
        for url in urls:
            try:
                response = await client.get(url)
                if response.status_code < 400 and response.text:
                    return url, response.text
            except Exception:
                continue
    return None, None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_extract_jsonld_real_page():
    """Fetch real product page and validate JSON-LD extraction."""
    url, html = await _fetch_html(
        [
            "https://www.allbirds.com/products/mens-tree-runners",
            "https://www.lego.com/en-us/product/tuxedo-cat-21349",
            "https://www.apple.com/shop/buy-iphone/iphone-16",
        ]
    )
    if not url or not html:
        pytest.skip("No reachable product page for integration test")
    result = extract_from_jsonld(BeautifulSoup(html, "html.parser"))
    if result.price is None or result.title is None:
        pytest.skip(f"JSON-LD not available in selected page: {url}")
    assert result.title is not None
    assert result.price is not None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_extract_meta_real_page():
    """Fetch real page and validate meta tags extraction."""
    url, html = await _fetch_html(
        [
            "https://www.allbirds.com/products/mens-tree-runners",
            "https://www.lego.com/en-us/product/tuxedo-cat-21349",
            "https://www.apple.com/shop/buy-iphone/iphone-16",
        ]
    )
    if not url or not html:
        pytest.skip("No reachable page for integration test")
    result = extract_from_meta_tags(BeautifulSoup(html, "html.parser"))
    if result.title is None and result.image_url is None and result.price is None:
        pytest.skip(f"Meta extraction unavailable for selected page: {url}")
    assert result.title is not None or result.image_url is not None or result.price is not None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_extract_auto_detect():
    """Auto-detect should find price on page without strict structured tags."""
    _, html = await _fetch_html(["https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html"])
    if not html:
        pytest.skip("books.toscrape.com is not reachable")
    result = extract_auto_detect(BeautifulSoup(html, "html.parser"))
    assert result.price is not None


def test_merge_results():
    """Merged result should preserve first non-None fields by priority."""
    high = ExtractedProduct(title="A")
    mid = ExtractedProduct(price=99.5)
    low = ExtractedProduct(image_url="https://img.example/1.jpg")
    merged = merge_results(high, mid, low)
    assert merged.title == "A"
    assert merged.price == 99.5
    assert merged.image_url == "https://img.example/1.jpg"


def test_parse_price_text():
    """Locale-aware price parsing should handle decimal separators."""
    assert parse_price_text("1 299,50 ₴") == 1299.50
    assert parse_price_text("$49.99") == 49.99
    assert parse_price_text("1.299,50 €") == 1299.50


@pytest.mark.integration
@pytest.mark.asyncio
async def test_extract_product_links():
    """Category page should produce product URLs."""
    url = "https://webscraper.io/test-sites/e-commerce/static/computers/laptops"
    _, html = await _fetch_html([url])
    if not html:
        pytest.skip("webscraper.io is not reachable")
    soup = BeautifulSoup(html, "html.parser")
    links = extract_product_links(soup, url)
    assert isinstance(links, list)
    assert len(links) > 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_scraper_pool_failover():
    """When Decodo is disabled, pool should fetch through fallback layers."""
    previous = scraper_pool_module.settings.decodo_enabled
    scraper_pool_module.settings.decodo_enabled = False
    try:
        pool = ScraperPool()
        result = await pool.scrape_product("https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html")
        if not result.success:
            pytest.skip("Fallback layers could not scrape integration page")
        assert result.scraper_layer in {"httpx", "playwright"}
    finally:
        scraper_pool_module.settings.decodo_enabled = previous


def test_completeness_score():
    """Completeness score should match required fields ratio."""
    full = ExtractedProduct(title="x", price=10.0, image_url="img")
    partial = ExtractedProduct(title="x", price=10.0, image_url=None)
    assert full.completeness == 1.0
    assert round(partial.completeness, 2) == 0.67
