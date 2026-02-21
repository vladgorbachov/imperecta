"""Generic web scraper with httpx + BeautifulSoup, fallback to Playwright."""

import re
from decimal import Decimal

import httpx
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

from app.scrapers.base import AbstractScraper, ScrapedData

COMMON_PRICE_SELECTORS = [
    '[itemprop="price"]',
    ".price",
    ".product-price",
    "[data-price]",
    ".current-price",
    "#price",
    ".price-block__final-price",
    "[class*='price']",
]


def _parse_price_text(text: str) -> Decimal | None:
    """Extract numeric price from string."""
    if not text:
        return None
    cleaned = re.sub(r"[^\d.,]", "", text.replace(" ", "").replace("\u00a0", ""))
    cleaned = cleaned.replace(",", ".")
    try:
        return Decimal(cleaned)
    except Exception:
        return None


class GenericWebScraper(AbstractScraper):
    """Generic scraper: httpx + BeautifulSoup, fallback to Playwright."""

    def __init__(self, css_selector_price: str | None = None) -> None:
        self._css_selector_price = css_selector_price

    def _extract_from_soup(self, soup: BeautifulSoup) -> ScrapedData | None:
        """Try to extract price from BeautifulSoup. Returns None if failed."""
        price = None
        selectors = (
            [self._css_selector_price] if self._css_selector_price else []
        ) + COMMON_PRICE_SELECTORS

        for sel in selectors:
            el = soup.select_one(sel)
            if el:
                price_text = el.get("content") or el.get("data-price") or el.get_text()
                price = _parse_price_text(price_text)
                if price is not None:
                    break

        if price is None:
            return None

        return ScrapedData(
            price=price,
            old_price=None,
            promo_label=None,
            in_stock=True,
            product_name=None,
        )

    async def _scrape_httpx(self, url: str) -> ScrapedData | None:
        """Fetch via httpx + BeautifulSoup."""
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
        }
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            response = await client.get(url, headers=headers)

        if response.status_code != 200:
            return None

        soup = BeautifulSoup(response.text, "lxml")
        return self._extract_from_soup(soup)

    async def _scrape_playwright(self, url: str) -> ScrapedData:
        """Fallback: fetch via Playwright and extract with same selectors."""
        selectors = (
            [self._css_selector_price] if self._css_selector_price else []
        ) + COMMON_PRICE_SELECTORS

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                page = await browser.new_page()
                page.set_default_timeout(15000)
                await page.goto(url, wait_until="domcontentloaded")
                await page.wait_for_load_state("networkidle", timeout=10000)

                price = None
                for sel in selectors:
                    el = await page.query_selector(sel)
                    if el:
                        content = await el.get_attribute("content")
                        data_price = await el.get_attribute("data-price")
                        text = await el.text_content()
                        price_text = content or data_price or text or ""
                        price = _parse_price_text(price_text)
                        if price is not None:
                            break

                if price is None:
                    raise ValueError("Could not extract price from page")

                return ScrapedData(
                    price=price,
                    old_price=None,
                    promo_label=None,
                    in_stock=True,
                    product_name=None,
                )
            finally:
                await browser.close()

    async def _scrape_impl(self, url: str) -> ScrapedData:
        """Try httpx first, fallback to Playwright if no data."""
        result = await self._scrape_httpx(url)
        if result is not None:
            return result
        return await self._scrape_playwright(url)
