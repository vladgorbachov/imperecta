"""
Imperecta scraping engine.

Universal scraper for any e-commerce site.
Primary: Decodo Web Scraping API (managed, handles anti-bot).
Fallback: Playwright + extraction strategies (JSON-LD, meta, DOM).
"""

import asyncio
import base64
import json
import logging
import random
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass

import httpx
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

from app.config import Settings
from app.scrapers.proxy_manager import proxy_manager

settings = Settings()

logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# ScrapeResult
# -----------------------------------------------------------------------------


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


# -----------------------------------------------------------------------------
# BaseScraper
# -----------------------------------------------------------------------------


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
            except Exception as e:
                last_error = e
                if attempt < self.MAX_RETRIES - 1:
                    backoff = self._backoff_delay(attempt)
                    await asyncio.sleep(backoff)
        raise last_error or RuntimeError("Scrape failed")

    async def _log_scrape(
        self,
        db,
        marketplace_id: str,
        marketplace_name: str,
        url: str,
        status: str,
        error_message: str | None = None,
        price_found: float | None = None,
        duration_ms: int | None = None,
        proxy_used: bool = False,
        competitor_product_id=None,
    ) -> None:
        """Log scrape result to scrape_logs table."""
        from app.models.scrape_log import ScrapeLog

        from decimal import Decimal

        price_val = Decimal(str(price_found)) if price_found is not None else None
        log = ScrapeLog(
            marketplace_id=marketplace_id,
            marketplace_name=marketplace_name,
            competitor_product_id=competitor_product_id,
            url=url,
            status=status,
            error_message=error_message,
            price_found=price_val,
            duration_ms=duration_ms,
            proxy_used=proxy_used,
        )
        db.add(log)


# -----------------------------------------------------------------------------
# UniversalScraper
# -----------------------------------------------------------------------------


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
        # Strategy 0: Decodo Web Scraping API (managed, handles anti-bot)
        if settings.decodo_enabled and settings.decodo_username:
            result = await self._scrape_decodo(url)
            if result and result.price:
                result.extraction_method = "decodo_api"
                result.product_url = url
                return result

        # Strategy 1-3: Playwright fallback (JSON-LD, meta, DOM)
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
        """
        Use Decodo Web Scraping API for managed scraping.
        Handles proxies, anti-bot, CAPTCHA automatically.
        """
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

        except Exception as e:
            logger.error("Decodo API error for %s: %s", url[:80], e)
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
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=True,
                    args=["--no-sandbox", "--disable-dev-shm-usage"],
                )
                context = await browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                    viewport={"width": 1920, "height": 1080},
                    **({"proxy": proxy_config} if proxy_config else {}),
                )
                page = await context.new_page()

                # Block images, fonts, media for speed
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

        except Exception as e:
            logger.error("Failed to fetch page %s: %s", url[:80], e)
            if proxy_config:
                self.proxy_manager.report_failure()
            return None

    def _extract_jsonld(self, html: str) -> ScrapeResult | None:
        """
        Extract product data from JSON-LD structured data.
        Most e-commerce sites include: <script type="application/ld+json">
        with @type: "Product" containing name, price, image, availability.
        """
        soup = BeautifulSoup(html, "html.parser")
        scripts = soup.find_all("script", type="application/ld+json")

        for script in scripts:
            try:
                data = json.loads(script.string or "{}")
            except (json.JSONDecodeError, TypeError):
                continue

            items = data if isinstance(data, list) else [data]

            for item in items:
                product = None

                if item.get("@type") == "Product":
                    product = item
                elif "@graph" in item:
                    for node in item["@graph"]:
                        if node.get("@type") == "Product":
                            product = node
                            break

                if not product:
                    continue

                price = None
                currency = None
                old_price = None

                offers = product.get("offers", {})
                if isinstance(offers, list):
                    offers = offers[0] if offers else {}
                elif isinstance(offers, str):
                    continue

                if "price" in offers:
                    price = self._parse_price(offers["price"])
                    currency = offers.get("priceCurrency")
                elif "lowPrice" in offers:
                    price = self._parse_price(offers["lowPrice"])
                    currency = offers.get("priceCurrency")
                    if "highPrice" in offers:
                        old_price = self._parse_price(offers["highPrice"])
                elif "highPrice" in offers:
                    price = self._parse_price(offers["highPrice"])
                    currency = offers.get("priceCurrency")

                if not price:
                    continue

                name = product.get("name")
                image = product.get("image")
                if isinstance(image, list):
                    image = image[0] if image else None
                elif isinstance(image, dict):
                    image = image.get("url")

                description = product.get("description", "")
                if isinstance(description, str) and len(description) > 500:
                    description = description[:500]

                availability = offers.get("availability", "")
                in_stock = "InStock" in str(availability) or "instock" in str(availability).lower()

                return ScrapeResult(
                    price=price,
                    old_price=old_price,
                    currency=currency,
                    product_name=name,
                    image_url=image,
                    description=description,
                    in_stock=in_stock,
                )

        return None

    def _extract_meta(self, html: str) -> ScrapeResult | None:
        """
        Extract product data from meta tags.
        Common patterns: og:price:amount, product:price:amount, og:title, og:image.
        """
        soup = BeautifulSoup(html, "html.parser")

        price = None
        currency = None

        price_metas = [
            ("og:price:amount", "og:price:currency"),
            ("product:price:amount", "product:price:currency"),
            ("twitter:data1", None),
        ]

        for price_prop, currency_prop in price_metas:
            meta = soup.find("meta", property=price_prop) or soup.find(
                "meta", attrs={"name": price_prop}
            )
            if meta and meta.get("content"):
                price = self._parse_price(meta["content"])
                if price:
                    if currency_prop:
                        cur_meta = soup.find("meta", property=currency_prop) or soup.find(
                            "meta", attrs={"name": currency_prop}
                        )
                        if cur_meta:
                            currency = cur_meta.get("content")
                    break

        if not price:
            return None

        name = None
        image = None

        for prop in ["og:title", "twitter:title"]:
            meta = soup.find("meta", property=prop) or soup.find("meta", attrs={"name": prop})
            if meta and meta.get("content"):
                name = meta["content"]
                break

        for prop in ["og:image", "twitter:image"]:
            meta = soup.find("meta", property=prop) or soup.find("meta", attrs={"name": prop})
            if meta and meta.get("content"):
                image = meta["content"]
                break

        return ScrapeResult(
            price=price,
            currency=currency,
            product_name=name,
            image_url=image,
        )

    async def _extract_dom_playwright(self, url: str) -> ScrapeResult | None:
        """
        Last resort: extract price from rendered DOM by pattern matching.
        Looks for common price patterns in visible text.
        """
        proxy_config = None
        if self.proxy_manager.is_available:
            proxy_config = self.proxy_manager.get_playwright_proxy(
                country=self._get_proxy_country(),
            )

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(
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

                price_selectors = [
                    '[data-price]',
                    '[data-product-price]',
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
                        el = await page.query_selector(selector)
                        if el:
                            data_price = await el.get_attribute("data-price")
                            if data_price:
                                price = self._parse_price(data_price)
                                if price:
                                    break

                            content = await el.get_attribute("content")
                            if content:
                                price = self._parse_price(content)
                                if price:
                                    break

                            text = await el.inner_text()
                            if text:
                                price = self._parse_price(text)
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
                    return ScrapeResult(
                        price=price,
                        product_name=title,
                        image_url=image,
                    )

        except Exception as e:
            logger.error("DOM extraction failed for %s: %s", url[:80], e)
            self.proxy_manager.report_failure()

        return None

    @staticmethod
    def _parse_price(value) -> float | None:
        """
        Parse price from various formats:
        "1 234.56", "1,234.56", "1234", "₽ 1 234", "$99.99", "11 265 ₽"
        """
        if value is None:
            return None

        s = str(value).strip()
        s = re.sub(r"[₽$€£¥₴₸₺₼₾₿\s]", " ", s)
        s = re.sub(
            r"(руб|сум|тг|грн|лей|zł|Kč|Ft|лв|kr|CHF|RUB|USD|EUR|UAH|KZT|PLN|RON|HUF|BGN|TRY|GBP)\.?",
            "",
            s,
            flags=re.IGNORECASE,
        )
        s = s.strip()

        if not s:
            return None

        match = re.search(r"(\d[\d\s.,]*\d|\d+)", s)
        if not match:
            return None

        num_str = match.group(1).replace(" ", "")

        if "," in num_str and "." in num_str:
            if num_str.rfind(",") > num_str.rfind("."):
                num_str = num_str.replace(".", "").replace(",", ".")
            else:
                num_str = num_str.replace(",", "")
        elif "," in num_str:
            parts = num_str.split(",")
            if len(parts[-1]) <= 2:
                num_str = num_str.replace(",", ".")
            else:
                num_str = num_str.replace(",", "")
        elif "." in num_str:
            parts = num_str.split(".")
            if len(parts[-1]) == 3 and len(parts) > 2:
                num_str = num_str.replace(".", "")

        try:
            result = float(num_str)
            return result if result > 0 else None
        except ValueError:
            return None


# -----------------------------------------------------------------------------
# ScraperFactory
# -----------------------------------------------------------------------------


class ScraperFactory:
    """Creates scraper instance. All scraper types now use UniversalScraper."""

    @classmethod
    def create(cls, scraper_type: str = "universal", **kwargs) -> BaseScraper:
        """Create scraper. scraper_type is ignored — always returns UniversalScraper."""
        return UniversalScraper(**kwargs)

    @classmethod
    def register(cls, scraper_type: str, scraper_class: type) -> None:
        """No-op. Kept for API compatibility. All types use UniversalScraper."""
        pass

    @classmethod
    def get_available_types(cls) -> list[str]:
        """List supported types (for stats). All map to UniversalScraper."""
        return ["universal"]
