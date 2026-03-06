"""
Imperecta scraping engine.

Contains all scraper implementations: Ozon, Wildberries, GenericWebScraper.
"""

import asyncio
import random
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal

import httpx
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

from app.scrapers.proxy_manager import proxy_manager


# -----------------------------------------------------------------------------
# ScrapeResult
# -----------------------------------------------------------------------------


@dataclass
class ScrapeResult:
    """Result of price scraping."""

    price: Decimal
    old_price: Decimal | None
    promo_label: str | None
    in_stock: bool
    product_name: str | None


# -----------------------------------------------------------------------------
# BaseScraper
# -----------------------------------------------------------------------------


class BaseScraper(ABC):
    """Abstract base class for marketplace scrapers with retries and delays."""

    MAX_RETRIES = 3
    DELAY_MIN = 1
    DELAY_MAX = 3

    _last_request_time: dict[str, float] = {}  # class-level, shared across instances

    def __init__(self, config: object | None = None) -> None:
        self.config = config
        self.proxy_manager = proxy_manager

    def _get_proxy_country(self) -> str | None:
        """Get country code for geo-targeted proxy from marketplace config."""
        if self.config and hasattr(self.config, "country"):
            return self.config.country
        return None

    def _get_sticky_key(self, url: str) -> str | None:
        """Generate sticky session key for multi-page scraping."""
        if self.config and hasattr(self.config, "id"):
            return f"{self.config.id}:{url[:100]}"
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

    async def scrape(self, url: str) -> ScrapeResult:
        """Scrape with retries (3 attempts, exponential backoff)."""
        await self._rate_limit()
        last_error: Exception | None = None
        for attempt in range(self.MAX_RETRIES):
            await self._random_delay()
            try:
                return await self._scrape_impl(url)
            except Exception as e:
                last_error = e
                if attempt < self.MAX_RETRIES - 1:
                    backoff = self._backoff_delay(attempt)
                    await asyncio.sleep(backoff)
        raise last_error or RuntimeError("Scrape failed")

    @abstractmethod
    async def _scrape_impl(self, url: str) -> ScrapeResult:
        """Implement actual scraping logic. Called by scrape() with retries."""
        pass


# -----------------------------------------------------------------------------
# OzonScraper
# -----------------------------------------------------------------------------


OZON_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
]


class OzonScraper(BaseScraper):
    """Ozon scraper using Playwright with headless Chromium."""

    def __init__(self, config: object | None = None) -> None:
        super().__init__(config)

    def _get_user_agent(self) -> str:
        """Rotate User-Agent."""
        return random.choice(OZON_USER_AGENTS)

    def _parse_price(self, text: str) -> Decimal | None:
        """Extract numeric price from string like '1 234 ₽' or '1234'."""
        if not text:
            return None
        cleaned = re.sub(r"[^\d.,]", "", text.replace(" ", "").replace("\u00a0", ""))
        cleaned = cleaned.replace(",", ".")
        try:
            return Decimal(cleaned)
        except Exception:
            return None

    async def _scrape_impl(self, url: str) -> ScrapeResult:
        """Scrape Ozon product page via Playwright."""
        proxy_config = self.proxy_manager.get_playwright_proxy(
            country=self._get_proxy_country(),
        )

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=True,
                    proxy=proxy_config,
                )
                try:
                    context = await browser.new_context(
                        user_agent=self._get_user_agent(),
                        viewport={"width": 1920, "height": 1080},
                    )
                    page = await context.new_page()
                    page.set_default_timeout(30000)

                    try:
                        response = await page.goto(url, wait_until="domcontentloaded")
                        if response and response.status == 404:
                            raise ValueError("Page not found")

                        await page.wait_for_load_state("networkidle", timeout=15000)
                    except PlaywrightTimeout:
                        self.proxy_manager.report_failure()
                        raise ValueError("Timeout loading page") from None
                    except Exception as e:
                        if "blocked" in str(e).lower() or "captcha" in str(e).lower():
                            self.proxy_manager.report_failure()
                        raise

                    price = None
                    old_price = None
                    promo_label = None
                    in_stock = True
                    product_name = None

                    price_el = await page.query_selector(
                        '[data-widget-name="webPrice"], [data-widget-name="webCurrentPrice"]'
                    )
                    if price_el:
                        price_text = await price_el.text_content()
                        price = self._parse_price(price_text or "")

                    if not price:
                        price_el = await page.query_selector(
                            ".t9q8 span:first-child, ._32-a2 span, [data-widget-name='webPrice'] span"
                        )
                        if price_el:
                            price_text = await price_el.text_content()
                            price = self._parse_price(price_text or "")

                    old_price_el = await page.query_selector(
                        "span[style*='line-through'], ._32-a3, .t9q9, [data-widget-name='webOldPrice']"
                    )
                    if old_price_el:
                        old_text = await old_price_el.text_content()
                        old_price = self._parse_price(old_text or "")

                    body_text = await page.inner_text("body")
                    if "Нет в наличии" in body_text or "нет в наличии" in body_text.lower():
                        in_stock = False

                    if "Скидка" in body_text or "скидка" in body_text.lower():
                        promo_label = "Скидка"
                    elif "Акция" in body_text or "акция" in body_text.lower():
                        promo_label = "Акция"

                    title_el = await page.query_selector("h1, [data-widget-name='webProductHeading']")
                    if title_el:
                        product_name = (await title_el.text_content() or "").strip()[:500]

                    if price is None:
                        raise ValueError("Could not extract price from page")

                    await context.close()
                    self.proxy_manager.report_success()
                    return ScrapeResult(
                        price=price,
                        old_price=old_price,
                        promo_label=promo_label,
                        in_stock=in_stock,
                        product_name=product_name,
                    )
                finally:
                    await browser.close()
        except Exception:
            self.proxy_manager.report_failure()
            raise


# -----------------------------------------------------------------------------
# WildberriesScraper
# -----------------------------------------------------------------------------


def _extract_wb_article_id(url: str) -> str | None:
    """Extract article_id (nm) from WB product URL."""
    match = re.search(r"/catalog/(\d+)/", url)
    if match:
        return match.group(1)
    match = re.search(r"/(\d+)\.html", url)
    if match:
        return match.group(1)
    return None


class WildberriesScraper(BaseScraper):
    """Wildberries scraper using card.wb.ru API."""

    def __init__(self, config: object | None = None) -> None:
        super().__init__(config)

    API_URL = "https://card.wb.ru/cards/v2/detail"
    DEFAULT_PARAMS = {
        "appType": "1",
        "curr": "rub",
        "dest": "-1257786",
    }

    async def _scrape_impl(self, url: str) -> ScrapeResult:
        """Fetch product data from WB card API."""
        article_id = _extract_wb_article_id(url)
        if not article_id:
            raise ValueError("Could not extract article_id from Wildberries URL")

        params = {**self.DEFAULT_PARAMS, "nm": article_id}
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json",
        }

        proxy_dict = self.proxy_manager.get_proxy(country=self._get_proxy_country())

        try:
            async with httpx.AsyncClient(
                proxies=proxy_dict,
                timeout=15.0,
            ) as client:
                response = await client.get(self.API_URL, params=params, headers=headers)

            if response.status_code != 200:
                raise ValueError(f"API returned {response.status_code}")

            self.proxy_manager.report_success()
            data = response.json()
        except Exception:
            self.proxy_manager.report_failure()
            raise

        products = data.get("data", {}).get("products", [])
        if not products:
            raise ValueError("Product not found in API response")

        product = products[0]

        sale_price = product.get("salePriceU")
        price_u = product.get("priceU")
        price = Decimal(sale_price) / 100 if sale_price is not None else None
        old_price = Decimal(price_u) / 100 if price_u and price_u != sale_price else None

        if price is None:
            raise ValueError("Could not extract price from API")

        sizes = product.get("sizes", [])
        in_stock = False
        for s in sizes:
            for st in s.get("stocks", []):
                if st.get("qty", 0) > 0:
                    in_stock = True
                    break
        if not sizes:
            in_stock = True

        sale = product.get("sale")
        promo_label = str(sale) if sale else None

        name = product.get("name")

        return ScrapeResult(
            price=price,
            old_price=old_price,
            promo_label=promo_label,
            in_stock=in_stock,
            product_name=name,
        )


# -----------------------------------------------------------------------------
# GenericWebScraper
# -----------------------------------------------------------------------------


def _random_user_agent() -> str:
    """Return random User-Agent for requests."""
    agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    ]
    return random.choice(agents)


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


class GenericWebScraper(BaseScraper):
    """Generic scraper: httpx + BeautifulSoup, fallback to Playwright."""

    def __init__(self, css_selector_price: str | None = None, config: object | None = None) -> None:
        super().__init__(config)
        self._css_selector_price = css_selector_price

    def _extract_from_soup(self, soup: BeautifulSoup) -> ScrapeResult | None:
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

        return ScrapeResult(
            price=price,
            old_price=None,
            promo_label=None,
            in_stock=True,
            product_name=None,
        )

    async def _scrape_httpx(self, url: str) -> ScrapeResult | None:
        """Fetch via httpx + BeautifulSoup."""
        proxy_dict = self.proxy_manager.get_proxy(country=self._get_proxy_country())
        try:
            async with httpx.AsyncClient(
                proxies=proxy_dict,
                timeout=30.0,
                follow_redirects=True,
                headers={"User-Agent": _random_user_agent()},
            ) as client:
                response = await client.get(url)

            if response.status_code != 200:
                return None

            self.proxy_manager.report_success()
            soup = BeautifulSoup(response.text, "lxml")
            return self._extract_from_soup(soup)
        except Exception:
            self.proxy_manager.report_failure()
            raise

    async def _scrape_playwright(self, url: str) -> ScrapeResult:
        """Fallback: fetch via Playwright and extract with same selectors."""
        selectors = (
            [self._css_selector_price] if self._css_selector_price else []
        ) + COMMON_PRICE_SELECTORS

        proxy_config = self.proxy_manager.get_playwright_proxy(
            country=self._get_proxy_country(),
        )

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=True,
                    proxy=proxy_config,
                )
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

                    return ScrapeResult(
                        price=price,
                        old_price=None,
                        promo_label=None,
                        in_stock=True,
                        product_name=None,
                    )
                finally:
                    await browser.close()
            self.proxy_manager.report_success()
        except Exception:
            self.proxy_manager.report_failure()
            raise

    async def _scrape_impl(self, url: str) -> ScrapeResult:
        """Try httpx first, fallback to Playwright if no data."""
        result = await self._scrape_httpx(url)
        if result is not None:
            return result
        return await self._scrape_playwright(url)


# -----------------------------------------------------------------------------
# ScraperFactory
# -----------------------------------------------------------------------------


class ScraperFactory:
    """Creates appropriate scraper instance based on scraper_type."""

    _registry: dict[str, type[BaseScraper]] = {
        "ozon": OzonScraper,
        "wildberries": WildberriesScraper,
        "generic": GenericWebScraper,
    }

    @classmethod
    def register(cls, scraper_type: str, scraper_class: type[BaseScraper]) -> None:
        """Register a new scraper type."""
        cls._registry[scraper_type] = scraper_class

    @classmethod
    def create(cls, scraper_type: str, **kwargs) -> BaseScraper:
        """Create scraper instance by type. Falls back to GenericWebScraper."""
        scraper_class = cls._registry.get(scraper_type, GenericWebScraper)
        return scraper_class(**kwargs)

    @classmethod
    def get_available_types(cls) -> list[str]:
        """List all registered scraper types."""
        return list(cls._registry.keys())
