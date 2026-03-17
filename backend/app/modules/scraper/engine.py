"""
Imperecta scraping engine.

Universal scraper for any e-commerce site.
Primary: Decodo Web Scraping API (managed, handles anti-bot).
Fallback: Playwright + extraction strategies (JSON-LD, meta, DOM).
"""

import asyncio
import base64
import logging
import random
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass

import httpx
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

from app.config import Settings
from app.modules.scraper.extractors import (
    extract_auto_detect,
    extract_from_jsonld,
    extract_from_meta_tags,
    parse_price_text,
)
from app.modules.scraper.proxy_manager import proxy_manager

settings = Settings()
logger = logging.getLogger(__name__)


@dataclass
class ScrapeResult:
    """Result of price scraping."""

    price: float | None = None
    old_price: float | None = None
    currency: str | None = None
    product_name: str | None = None
    image_url: str | None = None
    description: str | None = None
    in_stock: bool | None = None
    promo_label: str | None = None
    product_url: str | None = None
    extraction_method: str | None = None


class BaseScraper(ABC):
    """Abstract base class for marketplace scrapers with retries and delays."""

    MAX_RETRIES = 3
    DELAY_MIN = 1
    DELAY_MAX = 3
    _last_request_time: dict[str, float] = {}

    def __init__(self, config: object | None = None) -> None:
        self.config = config
        self.proxy_manager = proxy_manager

    def _get_proxy_country(self) -> str | None:
        """Get country code for geo-targeted proxy from marketplace config."""
        if self.config and hasattr(self.config, "country"):
            return self.config.country
        return None

    async def _rate_limit(self) -> None:
        """Enforce rate limit from marketplace config."""
        if not self.config or not hasattr(self.config, "id"):
            return
        key = str(self.config.id)
        rate = getattr(self.config, "rate_limit_seconds", 0) or 0
        if rate <= 0:
            return
        now = time.time()
        last = self._last_request_time.get(key, 0)
        wait = rate - (now - last)
        if wait > 0:
            await asyncio.sleep(wait)
        self._last_request_time[key] = time.time()

    async def _random_delay(self) -> None:
        """Random delay between requests (1-3 sec)."""
        delay = random.uniform(self.DELAY_MIN, self.DELAY_MAX)
        await asyncio.sleep(delay)

    def _backoff_delay(self, attempt: int) -> float:
        """Exponential backoff: 2^attempt seconds."""
        return 2**attempt

    @abstractmethod
    async def _scrape_impl(self, url: str) -> ScrapeResult:
        """Implement actual scraping logic. Called by scrape() with retries."""
        pass

    async def scrape(self, url: str) -> ScrapeResult:
        """Scrape with retries (3 attempts, exponential backoff)."""
        await self._rate_limit()
        last_error: Exception | None = None
        for attempt in range(self.MAX_RETRIES):
            await self._random_delay()
            try:
                return await self._scrape_impl(url)
            except Exception as error:
                last_error = error
                if attempt < self.MAX_RETRIES - 1:
                    backoff = self._backoff_delay(attempt)
                    await asyncio.sleep(backoff)
        raise last_error or RuntimeError("Scrape failed")


class UniversalScraper(BaseScraper):
    """
    Universal e-commerce scraper. Works with ANY online store.
    Strategy 0: Decodo Web Scraping API (primary, managed anti-bot).
    Strategy 1-3: Playwright fallback (JSON-LD, meta, DOM).
    """

    def __init__(self, config: object | None = None, css_selector_price: str | None = None) -> None:
        super().__init__(config)
        self._css_selector_price = css_selector_price

    async def _scrape_impl(self, url: str) -> ScrapeResult:
        """Main entry point. Decodo first, then Playwright fallback."""
        if settings.decodo_enabled and settings.decodo_username and settings.decodo_password:
            result = await self._scrape_decodo(url)
            if result and result.price:
                result.extraction_method = "decodo_api"
                result.product_url = url
                return result

        html = await self._fetch_page(url)
        if not html:
            raise ValueError("Failed to fetch page")

        result = self._extract_jsonld(html)
        if result and result.price:
            result.extraction_method = "jsonld"
            result.product_url = url
            return result

        result = self._extract_meta(html)
        if result and result.price:
            result.extraction_method = "meta"
            result.product_url = url
            return result

        result = await self._extract_dom_playwright(url)
        if result and result.price:
            result.extraction_method = "dom"
            result.product_url = url
            return result

        raise ValueError("Could not extract price from page")

    async def _scrape_decodo(self, url: str) -> ScrapeResult | None:
        """Use Decodo Web Scraping API for managed scraping."""
        auth = base64.b64encode(
            f"{settings.decodo_username}:{settings.decodo_password}".encode()
        ).decode()
        api_url = f"{settings.decodo_api_url.rstrip('/')}/scrape"
        payload = {
            "url": url,
            "headless": "html",
            "geo": self._get_geo_for_url(url),
        }

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    api_url,
                    json=payload,
                    headers={"Authorization": f"Basic {auth}"},
                )

            if resp.status_code != 200:
                logger.warning("Decodo API returned %d for %s", resp.status_code, url[:80])
                return None

            data = resp.json()
            results = data.get("results") or []
            first = results[0] if results else {}
            html = first.get("content") or data.get("html") or data.get("content") or ""

            if not isinstance(html, str):
                return None

            result = self._extract_jsonld(html)
            if result and result.price:
                return result

            result = self._extract_meta(html)
            if result and result.price:
                return result

            return None
        except Exception as error:
            logger.error("Decodo API error for %s: %s", url[:80], error)
            return None

    @staticmethod
    def _get_geo_for_url(url: str) -> str:
        """Detect geo location from URL domain."""
        domain = url.lower()
        if ".ru" in domain:
            return "ru"
        if ".ua" in domain:
            return "ua"
        if ".kz" in domain:
            return "kz"
        if ".de" in domain:
            return "de"
        if ".pl" in domain:
            return "pl"
        if ".fr" in domain:
            return "fr"
        if ".ro" in domain:
            return "ro"
        return "eu"

    async def _fetch_page(self, url: str) -> str | None:
        """Fetch page HTML. Uses Playwright for JS-rendered sites."""
        proxy_config = None
        if self.proxy_manager.is_available:
            proxy_config = self.proxy_manager.get_playwright_proxy(
                country=self._get_proxy_country(),
            )

        try:
            async with async_playwright() as playwright:
                browser = await playwright.chromium.launch(
                    headless=True,
                    args=["--no-sandbox", "--disable-dev-shm-usage"],
                )
                context = await browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                    viewport={"width": 1920, "height": 1080},
                    **({"proxy": proxy_config} if proxy_config else {}),
                )
                page = await context.new_page()

                async def block_heavy(route):
                    if route.request.resource_type in ("image", "font", "media"):
                        await route.abort()
                    else:
                        await route.continue_()

                await page.route("**/*", block_heavy)
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(3000)
                html = await page.content()
                await browser.close()
                if proxy_config:
                    self.proxy_manager.report_success()
                return html
        except Exception as error:
            logger.error("Failed to fetch page %s: %s", url[:80], error)
            if proxy_config:
                self.proxy_manager.report_failure()
            return None

    def _extract_jsonld(self, html: str) -> ScrapeResult | None:
        """Extract product data from JSON-LD structured data."""
        extracted = extract_from_jsonld(BeautifulSoup(html, "html.parser"))
        if extracted.price is None:
            return None
        return ScrapeResult(
            price=extracted.price,
            old_price=extracted.original_price,
            currency=extracted.currency,
            product_name=extracted.title,
            image_url=extracted.image_url,
            description=extracted.description,
            in_stock=None,
        )

    def _extract_meta(self, html: str) -> ScrapeResult | None:
        """Extract product data from meta tags."""
        extracted = extract_from_meta_tags(BeautifulSoup(html, "html.parser"))
        if extracted.price is None:
            return None
        return ScrapeResult(
            price=extracted.price,
            old_price=extracted.original_price,
            currency=extracted.currency,
            product_name=extracted.title,
            image_url=extracted.image_url,
            description=extracted.description,
            in_stock=None,
        )

    async def _extract_dom_playwright(self, url: str) -> ScrapeResult | None:
        """Last resort: extract price from rendered DOM by pattern matching."""
        proxy_config = None
        if self.proxy_manager.is_available:
            proxy_config = self.proxy_manager.get_playwright_proxy(
                country=self._get_proxy_country(),
            )

        try:
            async with async_playwright() as playwright:
                browser = await playwright.chromium.launch(
                    headless=True,
                    args=["--no-sandbox", "--disable-dev-shm-usage"],
                )
                context = await browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    viewport={"width": 1920, "height": 1080},
                    **({"proxy": proxy_config} if proxy_config else {}),
                )
                page = await context.new_page()
                await page.goto(url, wait_until="networkidle", timeout=30000)
                await page.wait_for_timeout(3000)
                html = await page.content()

                price_selectors = [
                    "[data-price]",
                    "[data-product-price]",
                    '[itemprop="price"]',
                    ".product-price",
                    ".price-current",
                    ".price-new",
                    ".current-price",
                    ".sale-price",
                    ".final-price",
                    '[class*="price" i][class*="current" i]',
                    '[class*="price" i][class*="main" i]',
                    '[class*="price" i][class*="final" i]',
                    ".price-block__final-price",
                    ".product-page__price-new",
                    '[data-widget="webPrice"]',
                    ".price",
                    "#price",
                ]

                if self._css_selector_price:
                    price_selectors.insert(0, self._css_selector_price)

                price = None
                for selector in price_selectors:
                    try:
                        element = await page.query_selector(selector)
                        if element:
                            data_price = await element.get_attribute("data-price")
                            if data_price:
                                price = parse_price_text(data_price)
                                if price:
                                    break

                            content = await element.get_attribute("content")
                            if content:
                                price = parse_price_text(content)
                                if price:
                                    break

                            text = await element.inner_text()
                            if text:
                                price = parse_price_text(text)
                                if price:
                                    break
                    except Exception:
                        continue

                title = await page.title()
                image = None
                try:
                    og_img = await page.query_selector('meta[property="og:image"]')
                    if og_img:
                        image = await og_img.get_attribute("content")
                except Exception:
                    pass

                await browser.close()

                if price:
                    self.proxy_manager.report_success()
                    auto = extract_auto_detect(BeautifulSoup(html, "html.parser"), url)
                    return ScrapeResult(
                        price=price,
                        product_name=auto.title or title,
                        image_url=auto.image_url or image,
                        description=auto.description,
                    )
        except Exception as error:
            logger.error("DOM extraction failed for %s: %s", url[:80], error)
            self.proxy_manager.report_failure()

        return None


class ScraperFactory:
    """Creates scraper instance. All scraper types now use UniversalScraper."""

    @classmethod
    def create(cls, scraper_type: str = "universal", **kwargs) -> BaseScraper:
        """Create scraper. scraper_type is ignored - always returns UniversalScraper."""
        return UniversalScraper(**kwargs)
