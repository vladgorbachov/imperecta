"""Ozon marketplace scraper using Playwright."""

import random
import re
from decimal import Decimal

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

from app.scrapers.base import AbstractScraper, ScrapedData
from app.scrapers.proxy_manager import ProxyManager

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
]


class OzonScraper(AbstractScraper):
    """Ozon scraper using Playwright with headless Chromium."""

    def __init__(self) -> None:
        self._proxy_manager = ProxyManager()

    def _get_user_agent(self) -> str:
        """Rotate User-Agent."""
        return random.choice(USER_AGENTS)

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

    async def _scrape_impl(self, url: str) -> ScrapedData:
        """Scrape Ozon product page via Playwright."""
        proxy = self._proxy_manager.get_proxy()
        proxy_config = {"server": proxy} if proxy else None

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                context = await browser.new_context(
                    user_agent=self._get_user_agent(),
                    proxy=proxy_config,
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
                    if proxy:
                        self._proxy_manager.mark_failed(proxy)
                    raise ValueError("Timeout loading page")
                except Exception as e:
                    if "blocked" in str(e).lower() or "captcha" in str(e).lower():
                        if proxy:
                            self._proxy_manager.mark_failed(proxy)
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
            finally:
                await browser.close()

        return ScrapedData(
            price=price,
            old_price=old_price,
            promo_label=promo_label,
            in_stock=in_stock,
            product_name=product_name,
        )
