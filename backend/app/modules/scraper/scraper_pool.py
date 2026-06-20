"""
Unified scraping interface with automatic failover and completeness checking.

Fetch backend priority: proxy provider API -> direct HTTP -> browser render
Data extraction: JSON-LD -> meta -> custom selectors -> auto-detect -> merge
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field

from bs4 import BeautifulSoup

from app.modules.classifier import classify_page_role_for_discovery
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
from app.modules.scraper.fetch_backends import (
    BackendId,
    ProxyProviderBackend,
    backend_id_persisted,
    get_fetch_backend,
)
from app.modules.scraper.proxy_provider_limiter import PROXY_PROVIDER_DEADLINE_ERROR

logger = logging.getLogger(__name__)

# Per-backend fetch: retries (timeouts / transient failures) before trying next backend.
FETCH_ATTEMPTS_PER_LAYER = 3
RETRY_BACKOFF_SEC = 0.45
# Cap raw HTML attached to PoolScrapeResult when proxy provider is off (debug only).
_MAX_DEBUG_RAW_HTML_CHARS = 200_000
_NON_RETRIABLE_LAYER_ERRORS = {"not_found", "blocked", "captcha", "rate_limit"}
# Tiered scrape strategy: which fetch backends are eligible for each tier.
# Backend order within a tier is determined by _layer_order() based on requires_js
# (kept as a fine-grained hint inside a tier).
#
# Tier 1: server-rendered shops. Default for newly-added marketplaces.
#   Uses the existing proxy_provider / direct_http / browser_render cascade.
#
# Tier 2: modern SPA shops (placeholder — not implemented yet, see _layer_order).
#   When activated, this tier will add a browser intercept backend that
#   listens to XHR/fetch responses and extracts price from intercepted JSON
#   payloads, falling back to DOM if interception yields no result.
#
# Tier 3: hostile marketplaces (placeholder — not implemented yet).
#   Will add stealth browser render with anti-fingerprinting init scripts,
#   sticky residential proxy sessions per marketplace, and an LLM-extraction
#   fallback backend for pages where structured signals are absent.
#
# Activating tier 2 or 3 requires (a) implementing the corresponding backend
# in fetch_backends and (b) updating _layer_order to include them.
# Until then, requesting tier > 1 raises NotImplementedError so that misconfigured
# marketplaces fail loudly rather than silently falling back to tier 1 behavior.
_SUPPORTED_SCRAPE_TIERS = frozenset({1})
_KNOWN_SCRAPE_TIERS = frozenset({1, 2, 3})


def _would_escalate_shell(
    *,
    scrape_tier: int,
    used_backend: BackendId | None,
    merged_currency: str | None,
    role: str,
) -> bool:
    """Pure structural predicate for the Z-JSDETECT shell detector.

    Observe-only today; ENFORCE may flip the call site to actually escalate.
    A scrape_product result on a Tier-1 direct HTTP fetch is treated as a likely
    JS-shell when the extractor produced NO currency AND the page does not
    classify as a product. Both signals empty = genuine shell; either signal
    present = the page yielded structured product data, no escalation needed.

    Universal/structural — keys only off scrape_tier (policy gate), used_backend
    (the free backend we'd escalate FROM), merged.currency (extractor verdict),
    and the classifier's page-role (DOM verdict). No marketplace names, no
    per-shop branching.
    """
    return (
        scrape_tier == 1
        and used_backend == BackendId.DIRECT_HTTP
        and merged_currency is None
        and role != "product"
    )


@dataclass
class ListingFetchResult:
    """Network-only fetch outcome for one listing URL (no extraction)."""

    html: str | None
    used_backend: BackendId | None
    last_error: str
    duration_ms: int
    deadline_skipped: bool = False


@dataclass
class PoolScrapeResult:
    """Result of scraping a single product URL.

    Field groups:
    - System/mandatory: success, url, error
    - Extracted data container: data
    - Technical: fetch_backend, duration_ms
    - Derived quality flags: is_partial, is_empty, extracted_fields, missing_fields
    - Persistence: log_status (set by GlobalScrapeService); raw_html when debugging
      without proxy provider
    """

    # System
    success: bool
    url: str
    error: str | None = None

    # Extracted data container
    data: ExtractedProduct | None = None

    # Technical
    fetch_backend: str | None = None
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
    fetch_backend: str | None = None
    error: str | None = None


class ScraperPool:
    """Priority: proxy provider API -> direct HTTP -> browser render.

    Fetches HTML once per URL, runs JSON-LD/meta/custom/auto extractors, and
    retries each transport with backoff before trying the next backend.
    """

    async def scrape_product(
        self,
        url: str,
        custom_selectors: dict | None = None,
        requires_js: bool = False,
        *,
        scrape_tier: int = 1,
        deadline_monotonic: float | None = None,
    ) -> PoolScrapeResult:
        """
        Fetch HTML once (proxy provider -> direct HTTP -> browser render), extract once.
        Do NOT re-fetch via browser render after proxy provider returns HTML.
        """
        fetch = await self.fetch_listing_html(
            url,
            requires_js=requires_js,
            scrape_tier=scrape_tier,
            deadline_monotonic=deadline_monotonic,
        )
        if fetch.deadline_skipped:
            return PoolScrapeResult(
                success=False,
                url=url,
                error=PROXY_PROVIDER_DEADLINE_ERROR,
                data=None,
                fetch_backend=None,
                duration_ms=fetch.duration_ms,
                is_empty=True,
            )
        return self.build_scrape_result_from_html(
            fetch.html,
            url,
            custom_selectors=custom_selectors,
            used_backend=fetch.used_backend,
            duration_ms=fetch.duration_ms,
            last_error=fetch.last_error,
            scrape_tier=scrape_tier,
            requires_js=requires_js,
        )

    async def fetch_listing_html(
        self,
        url: str,
        *,
        requires_js: bool = False,
        scrape_tier: int = 1,
        deadline_monotonic: float | None = None,
    ) -> ListingFetchResult:
        """Fetch HTML for one listing URL without extraction."""
        started = time.perf_counter()
        backend_ids = self._layer_order(requires_js=requires_js, scrape_tier=scrape_tier)

        html = None
        used_backend: BackendId | None = None
        last_error = "fetch_failed"
        deadline_skipped = False
        for backend_id in backend_ids:
            backend_started = time.perf_counter()
            html, backend_err = await self._fetch_layer_with_retries(
                backend_id,
                url,
                deadline_monotonic=deadline_monotonic,
            )
            backend_ms = int((time.perf_counter() - backend_started) * 1000)
            logger.info(
                "scrape_backend backend=%s duration_ms=%s ok=%s error=%s url=%s",
                backend_id.value,
                backend_ms,
                bool(html),
                (backend_err or "")[:500],
                url[:120],
            )
            logger.info(
                "fetch_backend_attempt backend=%s duration_ms=%s ok=%s error_preview=%s url=%s",
                backend_id.value,
                backend_ms,
                bool(html),
                ((backend_err or "")[:300] if backend_err else None),
                url[:200],
            )
            if backend_err == PROXY_PROVIDER_DEADLINE_ERROR:
                deadline_skipped = True
                break
            if html:
                used_backend = backend_id
                break
            if backend_err:
                last_error = backend_err

        duration_ms = int((time.perf_counter() - started) * 1000)
        return ListingFetchResult(
            html=html,
            used_backend=used_backend,
            last_error=last_error,
            duration_ms=duration_ms,
            deadline_skipped=deadline_skipped and not html,
        )

    def build_scrape_result_from_html(
        self,
        html: str | None,
        url: str,
        *,
        custom_selectors: dict | None,
        used_backend: BackendId | None,
        duration_ms: int,
        last_error: str = "fetch_failed",
        scrape_tier: int = 1,
        requires_js: bool = False,
    ) -> PoolScrapeResult:
        """Build a PoolScrapeResult from fetched HTML (sync extraction only)."""
        fetch_backend = backend_id_persisted(used_backend)
        raw_debug: str | None = None
        if html and not ProxyProviderBackend.is_enabled():
            raw_debug = html[:_MAX_DEBUG_RAW_HTML_CHARS]

        if not html:
            return PoolScrapeResult(
                success=False,
                url=url,
                error=last_error,
                data=None,
                fetch_backend=None,
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
                fetch_backend=fetch_backend,
                duration_ms=duration_ms,
                raw_html=raw_debug,
            )

        try:
            if (
                scrape_tier == 1
                and used_backend == BackendId.DIRECT_HTTP
                and merged.currency is None
            ):
                probe_soup = BeautifulSoup(html, "html.parser")
                role = classify_page_role_for_discovery(probe_soup, url)
                if _would_escalate_shell(
                    scrape_tier=scrape_tier,
                    used_backend=used_backend,
                    merged_currency=merged.currency,
                    role=role,
                ):
                    backend_ids = self._layer_order(
                        requires_js=requires_js,
                        scrape_tier=scrape_tier,
                    )
                    remaining = [
                        backend
                        for backend in backend_ids
                        if used_backend
                        and backend_ids.index(backend) > backend_ids.index(used_backend)
                    ]
                    next_backend = remaining[0] if remaining else None
                    logger.info(
                        "js_shell_would_escalate observe_only=1 url=%s "
                        "marketplace_backend=%s next_backend=%s role=%s "
                        "title_present=%s price_present=%s",
                        url[:200],
                        used_backend.value if used_backend else None,
                        next_backend.value if next_backend else None,
                        role,
                        bool(merged.title),
                        merged.price is not None,
                    )
        except Exception:
            pass

        if merged.price is not None and merged.price <= 0:
            merged.price = None
        if merged.price is None:
            return PoolScrapeResult(
                success=False,
                url=url,
                error="price_not_found",
                data=None,
                fetch_backend=fetch_backend,
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
            "fetch_extract_complete backend=%s duration_ms=%s "
            "fields_extracted=%s fields_missing=%s "
            "price_raw_text=%s currency_raw=%s "
            "detected_currency=%s title_preview=%s price_numeric=%s",
            fetch_backend,
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
            "Scraping %s: backend=%s, title=%s, price=%s",
            url[:80],
            fetch_backend,
            merged.title[:50] if merged.title else None,
            merged.price,
        )

        return PoolScrapeResult(
            success=True,
            url=url,
            error=None,
            data=merged,
            fetch_backend=fetch_backend,
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
        """Fetch raw HTML via fetch backends. Used by Discovery."""
        backend_ids = self._layer_order(requires_js=requires_js, scrape_tier=scrape_tier)
        for backend_id in backend_ids:
            html, _err = await self._fetch_layer_with_retries(backend_id, url)
            if html:
                return html
        return None

    async def _fetch_raw(
        self, url: str, requires_js: bool = False, *, scrape_tier: int = 1
    ) -> str | None:
        """Fetch and return raw HTML/text for a URL without extraction.

        Tries fetch backends in priority order. Returns None on total failure.
        """
        backend_ids = self._layer_order(requires_js=requires_js, scrape_tier=scrape_tier)
        for backend_id in backend_ids:
            try:
                html, _err = await self._fetch_layer_with_retries(backend_id, url)
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

        Order: direct HTTP (fast, free) -> proxy provider without JS render.
        Browser render is intentionally excluded: static content does not need a browser,
        and if both direct HTTP and proxy-provider bypass fail, the document is likely
        unavailable rather than JS-gated.
        """
        started = time.perf_counter()
        for backend_id, render_js in (
            (BackendId.DIRECT_HTTP, True),
            (BackendId.PROXY_PROVIDER, False),
        ):
            backend_started = time.perf_counter()
            html, backend_err = await self._fetch_layer_with_retries(
                backend_id,
                url,
                render_js=render_js,
            )
            backend_ms = int((time.perf_counter() - backend_started) * 1000)
            logger.info(
                "fetch_static_backend backend=%s duration_ms=%s ok=%s error=%s url=%s",
                backend_id.value,
                backend_ms,
                bool(html),
                (backend_err or "")[:300],
                (log_url_hint or url)[:200],
            )
            if html:
                total_ms = int((time.perf_counter() - started) * 1000)
                logger.info(
                    "fetch_static_done backend_won=%s duration_ms=%s url=%s",
                    backend_id.value,
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
        """Fetch sitemap XML via static backends, then browser render as fallback."""
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
        backend_ids = self._layer_order(requires_js=requires_js)
        for backend_id in backend_ids:
            html, _err = await self._fetch_layer_with_retries(backend_id, url)
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
                    fetch_backend=backend_id_persisted(backend_id),
                )
        return ListingScrapeResult(
            success=False,
            url=url,
            product_urls=[],
            error="listing_fetch_failed",
        )

    async def _fetch_layer_with_retries(
        self,
        backend_id: BackendId,
        url: str,
        *,
        render_js: bool = True,
        deadline_monotonic: float | None = None,
    ) -> tuple[str | None, str | None]:
        """Try backend up to FETCH_ATTEMPTS_PER_LAYER times; return (html, last_error_code)."""
        last_code: str | None = None
        for attempt in range(FETCH_ATTEMPTS_PER_LAYER):
            html, err = await self._fetch_by_backend_once(
                backend_id,
                url,
                render_js=render_js,
                deadline_monotonic=deadline_monotonic,
            )
            if html:
                return html, None
            last_code = err or "fetch_failed"
            if last_code in _NON_RETRIABLE_LAYER_ERRORS:
                break
            if last_code == PROXY_PROVIDER_DEADLINE_ERROR:
                break
            if attempt < FETCH_ATTEMPTS_PER_LAYER - 1:
                await asyncio.sleep(RETRY_BACKOFF_SEC * (attempt + 1))
        mapped = self._map_layer_error(last_code, backend_id)
        if last_code == PROXY_PROVIDER_DEADLINE_ERROR:
            return None, PROXY_PROVIDER_DEADLINE_ERROR
        return None, mapped

    def _map_layer_error(self, code: str | None, backend_id: BackendId) -> str:
        backend_name = backend_id.value
        c = (code or "fetch_failed").lower()
        if c.startswith("timeout"):
            return f"timeout:{backend_name}"
        if c in {"blocked", "captcha", "not_found", "rate_limit"}:
            return f"{c}:{backend_name}"
        return f"fetch_failed:{backend_name}"

    async def _fetch_by_backend_once(
        self,
        backend_id: BackendId,
        url: str,
        *,
        render_js: bool = True,
        deadline_monotonic: float | None = None,
    ) -> tuple[str | None, str | None]:
        backend = get_fetch_backend(backend_id)
        return await backend.fetch(
            url,
            render_js=render_js,
            deadline_monotonic=deadline_monotonic,
        )

    def _layer_order(self, requires_js: bool, scrape_tier: int = 1) -> list[BackendId]:
        """Return the ordered list of fetch backends to try for one scrape attempt.

        Backend order is determined by two inputs:
        - scrape_tier: strategic policy choice (1/2/3) tied to marketplace category.
        - requires_js: fine-grained hint inside a tier (affects backend order, not set).

        Tier 1 (current default), policy B:
            Server-rendered (requires_js=False): direct_http -> proxy_provider -> browser_render.
                direct HTTP is FIRST to save proxy-provider quota — it is free/fast and
                sufficient for the server-rendered majority of Tier 1 shops.
                Proxy provider is tried only when direct HTTP fails; browser render last.
            JS-only (requires_js=True): proxy_provider -> browser_render -> direct_http.
                direct HTTP cannot execute JS, so leading with it on a JS-only page
                wastes a request. Proxy provider goes first when configured, then
                browser render. direct HTTP is kept as a last-resort fallback because
                some "JS" pages still expose partial server-rendered content.
            When proxy provider is not configured, it is dropped from both sequences.

        Tier 2 / Tier 3: backends are documented in _SUPPORTED_SCRAPE_TIERS and are
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

        proxy_provider_available = ProxyProviderBackend.is_configured()
        if requires_js:
            backends: list[BackendId] = []
            if proxy_provider_available:
                backends.append(BackendId.PROXY_PROVIDER)
            backends.append(BackendId.BROWSER_RENDER)
            backends.append(BackendId.DIRECT_HTTP)
            return backends
        backends = [BackendId.DIRECT_HTTP]
        if proxy_provider_available:
            backends.append(BackendId.PROXY_PROVIDER)
        backends.append(BackendId.BROWSER_RENDER)
        return backends

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
