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
    extract_from_microdata,
    extract_product_links,
    extract_with_custom_selectors,
    merge_and_finalize,
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
# Cap raw HTML attached to PoolScrapeResult when Decodo is off (debug only).
_MAX_DEBUG_RAW_HTML_CHARS = 200_000
_NON_RETRIABLE_LAYER_ERRORS = {"not_found", "blocked", "captcha", "rate_limit"}
# Tiered scrape strategy: which fetch layers are eligible for each tier.
# Layer order within a tier is determined by _layer_order() based on requires_js
# (kept as a fine-grained hint inside a tier).
#
# Tier 1: server-rendered shops. Default for newly-added marketplaces.
#   Uses the existing decodo / httpx / playwright cascade with current logic.
#
# Tier 2: modern SPA shops (placeholder — not implemented yet, see _layer_order).
#   When activated, this tier will add a "playwright_intercept" layer that
#   listens to XHR/fetch responses and extracts price from intercepted JSON
#   payloads, falling back to DOM if interception yields no result.
#
# Tier 3: hostile marketplaces (placeholder — not implemented yet).
#   Will add "playwright_stealth" with anti-fingerprinting init scripts,
#   sticky residential proxy sessions per marketplace, and an LLM-extraction
#   fallback layer for pages where structured signals are absent.
#
# Activating tier 2 or 3 requires (a) implementing the corresponding layer
# functions in ScraperPool and (b) updating _layer_order to include them.
# Until then, requesting tier > 1 raises NotImplementedError so that misconfigured
# marketplaces fail loudly rather than silently falling back to tier 1 behavior.
_SUPPORTED_SCRAPE_TIERS = frozenset({1})
_KNOWN_SCRAPE_TIERS = frozenset({1, 2, 3})


@dataclass
class PoolScrapeResult:
    """Result of scraping a single product URL.

    Field groups:
    - System/mandatory: success, url, error
    - Extracted data container: data
    - Technical: scraper_layer, duration_ms
    - Derived quality flags: is_partial, is_empty, extracted_fields, missing_fields
    - Persistence: log_status (set by GlobalScrapeService); raw_html when debugging without Decodo
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
    extracted_fields: list[str] = field(default_factory=list)
    missing_fields: list[str] = field(default_factory=list)
    log_status: str | None = None
    raw_html: str | None = None


@dataclass
class ListingScrapeResult:
    success: bool
    url: str
    product_urls: list[str] = field(default_factory=list)
    next_page_url: str | None = None
    scraper_layer: str | None = None
    error: str | None = None


class ScraperPool:
    """Priority: Decodo API -> httpx direct -> Playwright headless.

    Fetches HTML once per URL, runs JSON-LD/meta/custom/auto extractors, and
    retries each transport with backoff before trying the next layer.
    """

    async def scrape_product(
        self,
        url: str,
        custom_selectors: dict | None = None,
        requires_js: bool = False,
        *,
        scrape_tier: int = 1,
    ) -> PoolScrapeResult:
        """
        Fetch HTML once (Decodo -> httpx -> Playwright), extract once.
        Do NOT re-fetch via Playwright after Decodo returns HTML.
        """
        started = time.perf_counter()
        layers = self._layer_order(requires_js=requires_js, scrape_tier=scrape_tier)

        html = None
        used_layer = None
        last_error = "fetch_failed"
        for layer_name in layers:
            layer_started = time.perf_counter()
            html, layer_err = await self._fetch_layer_with_retries(layer_name, url)
            layer_ms = int((time.perf_counter() - layer_started) * 1000)
            logger.info(
                "scrape_layer layer=%s duration_ms=%s ok=%s error=%s url=%s",
                layer_name,
                layer_ms,
                bool(html),
                (layer_err or "")[:500],
                url[:120],
            )
            logger.info(
                "fetch_layer_attempt layer=%s duration_ms=%s ok=%s error_preview=%s url=%s",
                layer_name,
                layer_ms,
                bool(html),
                ((layer_err or "")[:300] if layer_err else None),
                url[:200],
            )
            if html:
                used_layer = layer_name
                break
            if layer_err:
                last_error = layer_err

        duration_ms = int((time.perf_counter() - started) * 1000)
        raw_debug: str | None = None
        if html and not settings.decodo_enabled:
            raw_debug = html[:_MAX_DEBUG_RAW_HTML_CHARS]

        if not html:
            return PoolScrapeResult(
                success=False,
                url=url,
                error=last_error,
                data=None,
                scraper_layer=None,
                duration_ms=duration_ms,
                is_empty=True,
                raw_html=raw_debug,
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
                raw_html=raw_debug,
            )

        if merged.price is not None and merged.price > MAX_VALID_PRICE:
            logger.warning(
                "Price overflow %.2f for %s, discarding",
                merged.price,
                url[:80],
            )
            return PoolScrapeResult(
                success=False,
                url=url,
                error="price_overflow",
                data=None,
                scraper_layer=used_layer,
                duration_ms=duration_ms,
                is_empty=not bool(merged.title),
                raw_html=raw_debug,
            )
        if merged.price is not None and merged.price <= 0:
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
                raw_html=raw_debug,
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

        logger.info(
            "fetch_extract_complete layer=%s duration_ms=%s "
            "fields_extracted=%s fields_missing=%s "
            "price_raw_text=%s currency_raw=%s "
            "detected_currency=%s title_preview=%s price_numeric=%s",
            used_layer,
            duration_ms,
            extracted_fields,
            missing_fields,
            getattr(merged, "price_raw_text", None),
            getattr(merged, "currency_raw", None),
            merged.currency,
            (merged.title[:80] if merged.title else None),
            merged.price,
        )
        logger.info(
            "Scraping %s: layer=%s, title=%s, price=%s",
            url[:80],
            used_layer,
            merged.title[:50] if merged.title else None,
            merged.price,
        )

        return PoolScrapeResult(
            success=True,
            url=url,
            error=None,
            data=merged,
            scraper_layer=used_layer,
            duration_ms=duration_ms,
            is_partial=is_partial,
            is_empty=is_empty,
            extracted_fields=extracted_fields,
            missing_fields=missing_fields,
            raw_html=raw_debug,
        )

    async def fetch_html(
        self, url: str, requires_js: bool = False, *, scrape_tier: int = 1
    ) -> str | None:
        """Fetch raw HTML via Decodo (primary) -> httpx -> Playwright. Used by Discovery."""
        layers = self._layer_order(requires_js=requires_js, scrape_tier=scrape_tier)
        for layer_name in layers:
            html, _err = await self._fetch_layer_with_retries(layer_name, url)
            if html:
                return html
        return None

    async def _fetch_raw(
        self, url: str, requires_js: bool = False, *, scrape_tier: int = 1
    ) -> str | None:
        """Fetch and return raw HTML/text for a URL without extraction.

        Tries fetch layers in priority order. Returns None on total failure.
        """
        layers = self._layer_order(requires_js=requires_js, scrape_tier=scrape_tier)
        for layer_name in layers:
            try:
                html, _err = await self._fetch_layer_with_retries(layer_name, url)
                if html:
                    return html
            except Exception:
                continue
        return None

    async def _fetch_static(
        self,
        url: str,
        *,
        log_url_hint: str | None = None,
    ) -> str | None:
        """Lightweight fetch for static documents (sitemap, robots, category/listing pages).

        Order: httpx (fast, free) -> decodo_static (anti-bot bypass without JS render).
        Playwright is intentionally excluded: static content does not need a browser,
        and if both httpx and Decodo proxy-bypass fail, the document is likely
        unavailable rather than JS-gated.
        """
        started = time.perf_counter()
        for layer_name in ("httpx", "decodo_static"):
            layer_started = time.perf_counter()
            html, layer_err = await self._fetch_layer_with_retries(layer_name, url)
            layer_ms = int((time.perf_counter() - layer_started) * 1000)
            logger.info(
                "fetch_static_layer layer=%s duration_ms=%s ok=%s error=%s url=%s",
                layer_name,
                layer_ms,
                bool(html),
                (layer_err or "")[:300],
                (log_url_hint or url)[:200],
            )
            if html:
                total_ms = int((time.perf_counter() - started) * 1000)
                logger.info(
                    "fetch_static_done layer_won=%s duration_ms=%s url=%s",
                    layer_name,
                    total_ms,
                    (log_url_hint or url)[:200],
                )
                return html
        total_ms = int((time.perf_counter() - started) * 1000)
        logger.info(
            "fetch_static_failed duration_ms=%s url=%s",
            total_ms,
            (log_url_hint or url)[:200],
        )
        return None

    @staticmethod
    def _looks_like_sitemap_xml(content: str) -> bool:
        """True when body is XML sitemap / index, not an HTML error page."""
        head = (content or "").lstrip()[:800].lower()
        return head.startswith("<?xml") or "<urlset" in head or "<sitemapindex" in head

    async def _fetch_sitemap_document(self, sitemap_url: str, *, log_hint: str) -> str | None:
        """Fetch sitemap XML via static layers, then Decodo HTML render as fallback."""
        content = await self._fetch_static(sitemap_url, log_url_hint=log_hint)
        if content and self._looks_like_sitemap_xml(content):
            return content
        html = await self._fetch_raw(sitemap_url, requires_js=True)
        if html and self._looks_like_sitemap_xml(html):
            logger.info(
                "sitemap_fetch_rendered_fallback url=%s",
                sitemap_url[:120],
            )
            return html
        return None

    async def fetch_sitemap_candidates(self, base_url: str) -> list[str]:
        """Attempt to discover and harvest product URLs from sitemaps."""
        from urllib.parse import urljoin

        from app.modules.scraper.extractors import (
            SITEMAP_MAX_SUBFILES,
            SITEMAP_MAX_URLS,
            parse_sitemap_xml,
        )

        sitemap_urls_to_try: list[str] = []

        robots_url = urljoin(base_url, "/robots.txt")
        try:
            robots_text = await self._fetch_static(
                robots_url,
                log_url_hint=f"{base_url} robots.txt",
            )
            if robots_text:
                for line in robots_text.splitlines():
                    line = line.strip()
                    if line.lower().startswith("sitemap:"):
                        sitemap_ref = line.split(":", 1)[1].strip()
                        if sitemap_ref:
                            sitemap_urls_to_try.append(sitemap_ref)
        except Exception:
            pass

        for path in ("/sitemap.xml", "/sitemap_index.xml", "/sitemap/sitemap.xml"):
            candidate = urljoin(base_url, path)
            if candidate not in sitemap_urls_to_try:
                sitemap_urls_to_try.append(candidate)

        product_urls: list[str] = []
        visited_sitemaps: set[str] = set()
        pending_sitemaps: list[str] = list(sitemap_urls_to_try)

        while pending_sitemaps and len(visited_sitemaps) < SITEMAP_MAX_SUBFILES:
            sitemap_url = pending_sitemaps.pop(0)
            if sitemap_url in visited_sitemaps:
                continue
            visited_sitemaps.add(sitemap_url)

            try:
                content = await self._fetch_sitemap_document(
                    sitemap_url,
                    log_hint=f"{base_url} sitemap",
                )
                if not content:
                    continue
            except Exception:
                continue

            parsed = parse_sitemap_xml(content, base_url)
            for nested in parsed["sitemaps"]:
                if nested not in visited_sitemaps:
                    pending_sitemaps.append(nested)
            for url in parsed["urls"]:
                if len(product_urls) >= SITEMAP_MAX_URLS:
                    break
                product_urls.append(url)
            if len(product_urls) >= SITEMAP_MAX_URLS:
                break

        return product_urls

    async def scrape_page_for_analysis(
        self,
        url: str,
        requires_js: bool = False,
        *,
        static_fetch: bool = False,
        scrape_tier: int = 1,
    ) -> tuple[str | None, BeautifulSoup | None]:
        """Fetch a page and return (html, soup) for structural analysis.

        Returns (None, None) on failure.
        """
        try:
            if static_fetch:
                html = await self._fetch_static(url)
            else:
                html = await self._fetch_raw(url, requires_js=requires_js, scrape_tier=scrape_tier)
            if not html:
                return None, None
            soup = BeautifulSoup(html, "html.parser")
            return html, soup
        except Exception:
            return None, None

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
            if last_code in _NON_RETRIABLE_LAYER_ERRORS:
                break
            if attempt < FETCH_ATTEMPTS_PER_LAYER - 1:
                await asyncio.sleep(RETRY_BACKOFF_SEC * (attempt + 1))
        mapped = self._map_layer_error(last_code, layer_name)
        return None, mapped

    def _map_layer_error(self, code: str | None, layer_name: str) -> str:
        c = (code or "fetch_failed").lower()
        if c.startswith("timeout"):
            return f"timeout:{layer_name}"
        if c in {"blocked", "captcha", "not_found", "rate_limit"}:
            return f"{c}:{layer_name}"
        return f"fetch_failed:{layer_name}"

    async def _fetch_by_layer_once(self, layer_name: str, url: str) -> tuple[str | None, str | None]:
        if layer_name == "decodo":
            return await self._fetch_html_decodo(url)
        if layer_name == "decodo_static":
            return await self._fetch_html_decodo_static(url)
        if layer_name == "httpx":
            return await self._fetch_html_httpx(url)
        if layer_name == "playwright":
            return await self._fetch_html_playwright(url)
        return None, "fetch_failed"

    def _layer_order(self, requires_js: bool, scrape_tier: int = 1) -> list[str]:
        """Return the ordered list of fetch-layer names to try for one scrape attempt.

        Layer order is determined by two inputs:
        - scrape_tier: strategic policy choice (1/2/3) tied to marketplace category.
        - requires_js: fine-grained hint inside a tier (affects layer order, not set).

        Tier 1 (current default), policy B:
            Server-rendered (requires_js=False): httpx -> decodo -> playwright.
                httpx is FIRST to save Decodo quota — httpx is free/fast and
                sufficient for the server-rendered majority of Tier 1 shops.
                Decodo is tried only when httpx fails; Playwright last.
            JS-only (requires_js=True): decodo -> playwright -> httpx.
                httpx cannot execute JS, so leading with it on a JS-only page
                wastes a request. Decodo (the primary scraper) goes first when
                configured, then Playwright. httpx is kept as a last-resort
                fallback because some "JS" pages still expose partial
                server-rendered content.
            When Decodo is not configured, "decodo" is dropped from both
            sequences.

        Tier 2 / Tier 3: layers are documented in _SUPPORTED_SCRAPE_TIERS and are
                         not yet implemented. They will be added when the platform
                         onboards marketplaces requiring them.

        Raises NotImplementedError when an unsupported tier is requested, so that
        operational misconfigurations surface immediately rather than silently
        degrading to Tier 1 behavior. Raises ValueError for unknown tier values
        (out of {1, 2, 3}) — this is a defensive API contract, separate from the
        DB CHECK constraint, and guards against programming errors in callers.
        """
        if scrape_tier not in _KNOWN_SCRAPE_TIERS:
            raise ValueError(
                f"Unknown scrape_tier={scrape_tier}; expected one of {sorted(_KNOWN_SCRAPE_TIERS)}"
            )
        if scrape_tier not in _SUPPORTED_SCRAPE_TIERS:
            raise NotImplementedError(
                f"scrape_tier={scrape_tier} layers not implemented yet; "
                f"currently supported tiers: {sorted(_SUPPORTED_SCRAPE_TIERS)}"
            )

        decodo_available = (
            settings.decodo_enabled
            and settings.decodo_username
            and settings.decodo_password
        )
        if requires_js:
            # JS-only page: httpx cannot execute JS, so lead with a JS-capable
            # transport. Decodo (the primary scraper) first when configured, then
            # Playwright, with httpx kept only as a last-resort fallback (some
            # "JS" pages still expose partial server-rendered content).
            layers: list[str] = []
            if decodo_available:
                layers.append("decodo")
            layers.append("playwright")
            layers.append("httpx")
            return layers
        # Server-rendered (general) case: httpx FIRST to save Decodo quota — httpx
        # is free/fast and sufficient for the server-rendered majority of Tier 1
        # shops. Decodo is tried only when httpx fails; Playwright last.
        layers = ["httpx"]
        if decodo_available:
            layers.append("decodo")
        layers.append("playwright")
        return layers

    async def _fetch_html_decodo_static(self, url: str) -> tuple[str | None, str | None]:
        return await self._fetch_html_decodo(url, render_js=False)

    async def _fetch_html_decodo(
        self,
        url: str,
        *,
        render_js: bool = True,
    ) -> tuple[str | None, str | None]:
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
        payload: dict[str, str] = {"url": url}
        if render_js:
            payload["headless"] = "html"
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
            if response.status_code == 429:
                return None, "rate_limit"
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
        jsonld = extract_from_jsonld(soup, url)
        # Level 1.5: HTML5 Microdata. Inserted BEFORE auto-detect so a
        # microdata-only Product page is structurally extracted instead of
        # falling through to the body-text fallback (which produces glued
        # currency_raw and gets gate-rejected). Order: jsonld > microdata >
        # meta > custom > auto.
        microdata = extract_from_microdata(soup, url)
        meta = extract_from_meta_tags(soup, url)
        custom = (
            extract_with_custom_selectors(soup, custom_selectors, url)
            if custom_selectors
            else ExtractedProduct()
        )
        auto = extract_auto_detect(soup, url)
        return merge_and_finalize(
            soup, url, jsonld, microdata, meta, custom, auto
        )
