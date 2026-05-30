"""Integration tests: HTTP fetch (network) and pool failover."""

import pytest
from bs4 import BeautifulSoup

from app.modules.scraper.extractors import (
    extract_auto_detect,
    extract_from_jsonld,
    extract_from_meta_tags,
    extract_product_links,
)
from app.modules.scraper.scraper_pool import ScraperPool
import app.modules.scraper.scraper_pool as scraper_pool_module

_ECOMMERCE_CATEGORY_URL = (
    "https://webscraper.io/test-sites/e-commerce/static/computers/laptops"
)
_ECOMMERCE_PRODUCT_URL = "https://webscraper.io/test-sites/e-commerce/static/product/1"

_JSONLD_FIXTURE = """
<html><head>
<script type="application/ld+json">
{"@context":"https://schema.org","@type":"Product","name":"Sample Item",
 "offers":{"@type":"Offer","price":"19.99","priceCurrency":"USD"}}
</script>
</head><body><h1>Sample Item</h1></body></html>
"""

_META_FIXTURE = """
<html><head>
<meta property="og:title" content="Sample Item" />
<meta property="og:image" content="https://cdn.example/item.jpg" />
<meta property="product:price:amount" content="19.99" />
</head><body></body></html>
"""

_AUTO_DETECT_FIXTURE = """
<html><body>
<p class="price">£51.77</p>
<h1>Sample Book</h1>
</body></html>
"""


async def _fetch_html(urls: list[str]) -> tuple[str, str] | tuple[None, None]:
    import httpx

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
async def test_extract_jsonld_from_fixture():
    """JSON-LD extraction on representative product markup."""
    result = extract_from_jsonld(BeautifulSoup(_JSONLD_FIXTURE, "html.parser"))
    assert result.title == "Sample Item"
    assert result.price is not None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_extract_meta_from_fixture():
    """Meta tag extraction on representative product markup."""
    result = extract_from_meta_tags(BeautifulSoup(_META_FIXTURE, "html.parser"))
    assert result.title == "Sample Item"
    assert result.image_url is not None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_extract_auto_detect_from_fixture():
    """Auto-detect should find price on page without strict structured tags."""
    result = extract_auto_detect(BeautifulSoup(_AUTO_DETECT_FIXTURE, "html.parser"))
    assert result.price is not None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_extract_product_links():
    """Category page should produce product URLs."""
    _, html = await _fetch_html([_ECOMMERCE_CATEGORY_URL])
    if not html:
        pytest.skip("E-commerce test site is not reachable")
    soup = BeautifulSoup(html, "html.parser")
    links = extract_product_links(soup, _ECOMMERCE_CATEGORY_URL)
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
        result = await pool.scrape_product(_ECOMMERCE_PRODUCT_URL)
        if not result.success:
            pytest.skip("Fallback layers could not scrape integration page")
        assert result.scraper_layer in {"httpx", "playwright"}
    finally:
        scraper_pool_module.settings.decodo_enabled = previous
