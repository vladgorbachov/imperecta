"""
Unified scraping interface with automatic failover and completeness checking.

HTTP layer priority: Decodo API -> httpx -> Playwright
Data extraction: JSON-LD -> meta -> custom selectors -> auto-detect -> merge
"""

import asyncio
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
MAX_VALID_PRICE = 9_999_999_999.99  # Max for Numeric(12,2)

# Per-layer fetch: retries (timeouts / transient failures) before trying next layer.
FETCH_ATTEMPTS_PER_LAYER = 3
RETRY_BACKOFF_SEC = 0.45
HTTP_TIMEOUT_SEC = 25.0
DECODO_TIMEOUT_SEC = 60.0
PLAYWRIGHT_GOTO_TIMEOUT_MS = 35_000
PLAYWRIGHT_WAIT_MS = 2_500


@dataclass
class PoolScrapeResult:
    """Result of scraping a single product URL.

    Field groups:
    - System/mandatory: success, url, error
    - Extracted data container: data
    - Technical: scraper_layer, duration_ms
    - Derived quality flags: is_partial, is_empty, fields_extracted, fields_missing
    """

    # System
    success: bool
    url: str
    error: str | None = None

    # Extracted data container
    data: ExtractedProduct | None = None

    # Technical
    scraper_layer: str | None = None
    duration_ms: int | None = None

    # Derived quality flags (populated by scraper_pool before return)
    is_partial: bool = False
    is_empty: bool = False
    fields_extracted: list[str] = field(default_factory=list)
    fields_missing: list[str] = field(default_factory=list)


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
        """
        Fetch HTML once (Decodo -> httpx -> Playwright), extract once.
        Do NOT re-fetch via Playwright after Decodo returns HTML.
        """
        started = time.perf_counter()
        layers = self._layer_order(requires_js=requires_js)

        html = None
        used_layer = None
        last_error = "fetch_failed"
        for layer_name in layers:
            html, layer_err = await self._fetch_layer_with_retries(layer_name, url)
            if html:
                used_layer = layer_name
                break
            if layer_err:
                last_error = layer_err

        duration_ms = int((time.perf_counter() - started) * 1000)
        if not html:
            return PoolScrapeResult(
                success=False,
                url=url,
                error=last_error,
                data=None,
                scraper_layer=None,
                duration_ms=duration_ms,
                is_empty=True,
            )

        try:
            merged = self._extract_all_levels(html, url, custom_selectors)
        except Exception as exc:
            logger.exception("extract_all_levels failed for %s", url[:120])
            return PoolScrapeResult(
                success=False,
                url=url,
                error=f"parse_error:{exc.__class__.__name__}",
                data=None,
                scraper_layer=used_layer,
                duration_ms=duration_ms,
            )

        if merged.price is not None and (
            merged.price > MAX_VALID_PRICE or merged.price <= 0
        ):
            logger.warning(
                "Price overflow %.2f for %s, discarding",
                merged.price,
                url[:80],
            )
            merged.price = None
        if merged.price is None:
            return PoolScrapeResult(
                success=False,
                url=url,
                error="price_not_found",
                data=None,
                scraper_layer=used_layer,
                duration_ms=duration_ms,
                is_empty=not bool(merged.title),
            )

        logger.info(
            "Scraping %s: layer=%s, title=%s, price=%s",
            url[:80],
            used_layer,
            merged.title[:50] if merged.title else None,
            merged.price,
        )
        extracted_fields: list[str] = []
        missing_fields: list[str] = []
        for field_name in ["title", "price", "currency", "in_stock", "image_url", "description"]:
            value = getattr(merged, field_name, None) if merged else None
            if value is not None and value != "":
                extracted_fields.append(field_name)
            else:
                missing_fields.append(field_name)

        cur_ok = bool(merged.currency and str(merged.currency).strip())
        is_partial = bool(
            (merged.price is not None and not merged.title)
            or not cur_ok
        )
        is_empty = merged.price is None and not merged.title

        return PoolScrapeResult(
            success=True,
            url=url,
            error=None,
            data=merged,
            scraper_layer=used_layer,
            duration_ms=duration_ms,
            is_partial=is_partial,
            is_empty=is_empty,
            fields_extracted=extracted_fields,
            fields_missing=missing_fields,
        )

    async def fetch_html(self, url: str, requires_js: bool = False) -> str | None:
        """Fetch raw HTML via Decodo (primary) -> httpx -> Playwright. Used by Discovery."""
        layers = self._layer_order(requires_js=requires_js)
        for layer_name in layers:
            html, _err = await self._fetch_layer_with_retries(layer_name, url)
            if html:
                return html
        return None

    async def scrape_listing(
        self,
        url: str,
        custom_link_selector: str | None = None,
        custom_next_page_selector: str | None = None,
        requires_js: bool = False,
    ) -> ListingScrapeResult:
        layers = self._layer_order(requires_js=requires_js)
        for layer_name in layers:
            html, _err = await self._fetch_layer_with_retries(layer_name, url)
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

    async def _fetch_layer_with_retries(
        self,
        layer_name: str,
        url: str,
    ) -> tuple[str | None, str | None]:
        """Try layer up to FETCH_ATTEMPTS_PER_LAYER times; return (html, last_error_code)."""
        last_code: str | None = None
        for attempt in range(FETCH_ATTEMPTS_PER_LAYER):
            html, err = await self._fetch_by_layer_once(layer_name, url)
            if html:
                return html, None
            last_code = err or "fetch_failed"
            if attempt < FETCH_ATTEMPTS_PER_LAYER - 1:
                await asyncio.sleep(RETRY_BACKOFF_SEC * (attempt + 1))
        mapped = self._map_layer_error(last_code, layer_name)
        return None, mapped

    def _map_layer_error(self, code: str | None, layer_name: str) -> str:
        c = (code or "fetch_failed").lower()
        if c.startswith("timeout"):
            return f"timeout:{layer_name}"
        if c in {"blocked", "captcha", "not_found"}:
            return f"{c}:{layer_name}"
        return f"fetch_failed:{layer_name}"

    async def _fetch_by_layer_once(self, layer_name: str, url: str) -> tuple[str | None, str | None]:
        if layer_name == "decodo":
            return await self._fetch_html_decodo(url)
        if layer_name == "httpx":
            return await self._fetch_html_httpx(url)
        if layer_name == "playwright":
            return await self._fetch_html_playwright(url)
        return None, "fetch_failed"

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

    async def _fetch_html_decodo(self, url: str) -> tuple[str | None, str | None]:
        """Fetch via Decodo API. Skip if disabled or credentials missing."""
        if not settings.decodo_enabled:
            return None, "fetch_failed"
        if not (settings.decodo_username and settings.decodo_password):
            logger.debug("Decodo credentials not configured, skipping")
            return None, "fetch_failed"
        auth = base64.b64encode(
            f"{settings.decodo_username}:{settings.decodo_password}".encode()
        ).decode()
        api_url = f"{settings.decodo_api_url.rstrip('/')}/scrape"
        payload = {"url": url, "headless": "html"}
        timeout = httpx.Timeout(DECODO_TIMEOUT_SEC)
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    api_url,
                    json=payload,
                    headers={"Authorization": f"Basic {auth}"},
                )
            if response.status_code == 404:
                return None, "not_found"
            if response.status_code in (403, 401):
                return None, "blocked"
            if response.status_code >= 400:
                return None, "fetch_failed"
            data = response.json()
            results = data.get("results") or []
            first = results[0] if results else {}
            html = first.get("content") or data.get("html") or data.get("content")
            if isinstance(html, str) and html.strip():
                return html, None
            return None, "fetch_failed"
        except httpx.TimeoutException:
            logger.warning("Decodo timeout for %s", url[:120])
            return None, "timeout"
        except httpx.HTTPStatusError as exc:
            logger.warning("Decodo HTTP error for %s: %s", url[:120], exc)
            return None, "fetch_failed"
        except Exception as exc:
            logger.warning("Decodo fetch failed for %s: %s", url[:120], exc)
            return None, "fetch_failed"

    async def _fetch_html_httpx(self, url: str) -> tuple[str | None, str | None]:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
            )
        }
        timeout = httpx.Timeout(HTTP_TIMEOUT_SEC)
        try:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                response = await client.get(url, headers=headers)
            if response.status_code == 404:
                return None, "not_found"
            if response.status_code in (403, 401):
                return None, "blocked"
            if response.status_code >= 400:
                return None, "fetch_failed"
            return response.text, None
        except httpx.TimeoutException:
            logger.warning("httpx timeout for %s", url[:120])
            return None, "timeout"
        except httpx.HTTPStatusError as exc:
            logger.warning("httpx HTTP error for %s: %s", url[:120], exc)
            return None, "fetch_failed"
        except Exception as exc:
            logger.warning("httpx fetch failed for %s: %s", url[:120], exc)
            return None, "fetch_failed"

    async def _fetch_html_playwright(self, url: str) -> tuple[str | None, str | None]:
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
                try:
                    resp = await page.goto(
                        url,
                        wait_until="domcontentloaded",
                        timeout=PLAYWRIGHT_GOTO_TIMEOUT_MS,
                    )
                    if resp is not None and resp.status == 404:
                        await browser.close()
                        return None, "not_found"
                    if resp is not None and resp.status in (401, 403):
                        await browser.close()
                        return None, "blocked"
                except Exception as exc:
                    await browser.close()
                    msg = str(exc).lower()
                    if "timeout" in msg or "timed out" in msg:
                        return None, "timeout"
                    return None, "fetch_failed"
                await page.wait_for_timeout(PLAYWRIGHT_WAIT_MS)
                html = await page.content()
                await browser.close()
                return html, None
        except Exception as exc:
            logger.warning("Playwright fetch failed for %s: %s", url[:120], exc)
            msg = str(exc).lower()
            if "timeout" in msg or "timed out" in msg:
                return None, "timeout"
            return None, "fetch_failed"

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
