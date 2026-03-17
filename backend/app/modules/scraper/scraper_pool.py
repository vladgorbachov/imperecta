"""
Unified scraping interface with automatic failover and completeness checking.

HTTP layer priority: Decodo API -> httpx -> Playwright
Data extraction: JSON-LD -> meta -> custom selectors -> auto-detect -> merge
"""

import base64
import logging
import time
from dataclasses import dataclass, field

import httpx
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

from app.config import Settings
from app.modules.scraper.extractors import (
    ExtractedProduct,
    detect_next_page,
    extract_auto_detect,
    extract_from_jsonld,
    extract_from_meta_tags,
    extract_product_links,
    extract_with_custom_selectors,
    merge_results,
)

logger = logging.getLogger(__name__)
settings = Settings()


@dataclass
class PoolScrapeResult:
    success: bool
    url: str
    data: ExtractedProduct | None = None
    scraper_layer: str | None = None
    duration_ms: int | None = None
    error: str | None = None


@dataclass
class ListingScrapeResult:
    success: bool
    url: str
    product_urls: list[str] = field(default_factory=list)
    next_page_url: str | None = None
    scraper_layer: str | None = None
    error: str | None = None


class ScraperPool:
    """Priority: Decodo API -> httpx direct -> Playwright headless."""

    async def scrape_product(
        self,
        url: str,
        custom_selectors: dict | None = None,
        requires_js: bool = False,
    ) -> PoolScrapeResult:
        started = time.perf_counter()
        layers = self._layer_order(requires_js=requires_js)

        merged = ExtractedProduct()
        used_layer = None

        for layer_name in layers:
            html = await self._fetch_by_layer(layer_name, url)
            if not html:
                continue
            used_layer = layer_name
            extracted = self._extract_all_levels(html, url, custom_selectors)
            merged = merge_results(merged, extracted)
            if merged.completeness >= 1.0:
                break

        duration_ms = int((time.perf_counter() - started) * 1000)
        if merged.price is None:
            return PoolScrapeResult(
                success=False,
                url=url,
                data=None,
                scraper_layer=used_layer,
                duration_ms=duration_ms,
                error="price_not_found",
            )

        return PoolScrapeResult(
            success=True,
            url=url,
            data=merged,
            scraper_layer=used_layer,
            duration_ms=duration_ms,
            error=None,
        )

    async def scrape_listing(
        self,
        url: str,
        custom_link_selector: str | None = None,
        custom_next_page_selector: str | None = None,
        requires_js: bool = False,
    ) -> ListingScrapeResult:
        layers = self._layer_order(requires_js=requires_js)
        for layer_name in layers:
            html = await self._fetch_by_layer(layer_name, url)
            if not html:
                continue
            soup = BeautifulSoup(html, "html.parser")
            product_urls = extract_product_links(
                soup=soup,
                base_url=url,
                custom_selector=custom_link_selector,
            )
            next_page_url = detect_next_page(
                soup=soup,
                current_url=url,
                custom_selector=custom_next_page_selector,
            )
            if product_urls or next_page_url:
                return ListingScrapeResult(
                    success=True,
                    url=url,
                    product_urls=product_urls,
                    next_page_url=next_page_url,
                    scraper_layer=layer_name,
                )
        return ListingScrapeResult(
            success=False,
            url=url,
            product_urls=[],
            error="listing_fetch_failed",
        )

    async def _fetch_by_layer(self, layer_name: str, url: str) -> str | None:
        if layer_name == "decodo":
            return await self._fetch_html_decodo(url)
        if layer_name == "httpx":
            return await self._fetch_html_httpx(url)
        if layer_name == "playwright":
            return await self._fetch_html_playwright(url)
        return None

    def _layer_order(self, requires_js: bool) -> list[str]:
        layers: list[str] = []
        if settings.decodo_enabled and settings.decodo_username and settings.decodo_password:
            layers.append("decodo")
        layers.append("httpx")
        layers.append("playwright")
        if requires_js and "playwright" in layers:
            layers = [layer for layer in layers if layer != "playwright"]
            layers.insert(1, "playwright")
        return layers

    async def _fetch_html_decodo(self, url: str) -> str | None:
        if not (settings.decodo_username and settings.decodo_password):
            return None
        auth = base64.b64encode(
            f"{settings.decodo_username}:{settings.decodo_password}".encode()
        ).decode()
        api_url = f"{settings.decodo_api_url.rstrip('/')}/scrape"
        payload = {"url": url, "headless": "html"}
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    api_url,
                    json=payload,
                    headers={"Authorization": f"Basic {auth}"},
                )
            if response.status_code != 200:
                return None
            data = response.json()
            results = data.get("results") or []
            first = results[0] if results else {}
            html = first.get("content") or data.get("html") or data.get("content")
            return html if isinstance(html, str) else None
        except Exception as exc:
            logger.warning("Decodo fetch failed for %s: %s", url[:120], exc)
            return None

    async def _fetch_html_httpx(self, url: str) -> str | None:
        try:
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
                )
            }
            async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
                response = await client.get(url, headers=headers)
            if response.status_code >= 400:
                return None
            return response.text
        except Exception as exc:
            logger.warning("httpx fetch failed for %s: %s", url[:120], exc)
            return None

    async def _fetch_html_playwright(self, url: str) -> str | None:
        try:
            async with async_playwright() as playwright:
                browser = await playwright.chromium.launch(
                    headless=True,
                    args=["--no-sandbox", "--disable-dev-shm-usage"],
                )
                context = await browser.new_context(
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
                    ),
                    viewport={"width": 1920, "height": 1080},
                )
                page = await context.new_page()
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(2500)
                html = await page.content()
                await browser.close()
                return html
        except Exception as exc:
            logger.warning("Playwright fetch failed for %s: %s", url[:120], exc)
            return None

    def _extract_all_levels(
        self,
        html: str,
        url: str,
        custom_selectors: dict | None,
    ) -> ExtractedProduct:
        soup = BeautifulSoup(html, "html.parser")
        jsonld = extract_from_jsonld(soup)
        meta = extract_from_meta_tags(soup)
        custom = (
            extract_with_custom_selectors(soup, custom_selectors)
            if custom_selectors
            else ExtractedProduct()
        )
        auto = extract_auto_detect(soup, url)
        return merge_results(jsonld, meta, custom, auto)
