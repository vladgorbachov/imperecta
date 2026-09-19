"""
Unified scraping interface with automatic failover and completeness checking.

Fetch backend priority: proxy provider API -> direct HTTP -> browser render
Data extraction: JSON-LD -> meta -> custom selectors -> auto-detect -> merge
"""

import asyncio
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from app.common.ops_alerts import emit_ops_alert
from app.modules.classifier import classify_page_role_for_discovery
from app.modules.scraper import access_policy, host_throttle, page_cache
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
from app.modules.scraper.proxy_provider_limiter import (
    PROXY_PROVIDER_DEADLINE_ERROR,
    PROXY_PROVIDER_SKIP_ERRORS,
    ProxyBudgetExhausted,
)
from app.observability.sentry_init import capture_exception_if_initialized

logger = logging.getLogger(__name__)

# Per-backend fetch: retries (timeouts / transient failures) before trying next backend.
FETCH_ATTEMPTS_PER_LAYER = 3
# The paid backend bills every attempt, failed ones included (Decodo
# dashboard 2026-09-19: 681 failed of 9,879 billed), so it gets exactly one
# try per fetch — the listing simply comes around again on its next tick.
PAID_BACKEND_ATTEMPTS = 1
RETRY_BACKOFF_SEC = 0.45
# Cap raw HTML attached to PoolScrapeResult when proxy provider is off (debug only).
_MAX_DEBUG_RAW_HTML_CHARS = 200_000
# A timeout is not retried inside the same fetch either: ldlc.com's direct
# tarpit (2026-09-19) cost 3 x 25s + 3 x 35s = 183s per listing and starved
# every PDP shard. The listing simply comes around again on its next tick.
_NON_RETRIABLE_LAYER_ERRORS = {"not_found", "blocked", "captcha", "rate_limit", "timeout"}
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

# Sitemap shard ordering for index walks: product shards first so a capped
# walk spends its budget on PDP URLs, chrome/editorial shards last. Substring
# hints are multilingual-structural (no per-shop branching).
_SITEMAP_PRODUCT_SHARD_HINTS = (
    "product",
    "produkt",
    "produs",
    "prekes",
    "preke",
    "tovar",
    "tavar",
    "goods",
    "item",
    "offer",
    "catalog",
    "katalog",
)
_SITEMAP_LATE_SHARD_HINTS = (
    "blog",
    "news",
    "article",
    "review",
    "static",
    "stranky",
    "pages",
    "category",
    "categories",
    "kategor",
    "brand",
    "filter",
    "image",
    "video",
)


def _sitemap_shard_priority(sitemap_url: str) -> int:
    """0 = product shard, 1 = neutral, 2 = editorial/navigation chrome.

    Hints are matched against the shard's file name with the word "sitemap"
    stripped — otherwise every shard matches the "item" hint via s-ITEM-ap.
    """
    name = sitemap_url.lower().rsplit("/", 1)[-1].replace("sitemap", "")
    if any(hint in name for hint in _SITEMAP_PRODUCT_SHARD_HINTS):
        return 0
    if any(hint in name for hint in _SITEMAP_LATE_SHARD_HINTS):
        return 2
    return 1


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
    # Which infra skip fired (deadline | budget); surfaces as the result error.
    deadline_skip_error: str = PROXY_PROVIDER_DEADLINE_ERROR


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
    page_role: str | None = None


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
                error=fetch.deadline_skip_error,
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
        render_js: bool | None = None,
    ) -> ListingFetchResult:
        """Fetch HTML for one listing URL without extraction.

        `render_js=False` asks the paid backend for the cheaper no-JS tier
        (list pages proven server-rendered); None leaves it to the shop's
        access_mode.
        """
        started = time.perf_counter()
        cached = page_cache.get_html(url)
        if cached:
            return ListingFetchResult(
                html=cached,
                used_backend=BackendId.PAGE_CACHE,
                last_error="",
                duration_ms=int((time.perf_counter() - started) * 1000),
            )
        backend_ids = self._layer_order(requires_js=requires_js, scrape_tier=scrape_tier, url=url)

        html = None
        used_backend: BackendId | None = None
        last_error = "fetch_failed"
        deadline_skipped = False
        deadline_skip_error = PROXY_PROVIDER_DEADLINE_ERROR
        for backend_id in backend_ids:
            backend_started = time.perf_counter()
            html, backend_err = await self._fetch_layer_with_retries(
                backend_id,
                url,
                render_js=render_js,
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
            if backend_err in PROXY_PROVIDER_SKIP_ERRORS:
                deadline_skipped = True
                deadline_skip_error = backend_err
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
            deadline_skip_error=deadline_skip_error,
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
            capture_exception_if_initialized(exc)
            return PoolScrapeResult(
                success=False,
                url=url,
                error=f"parse_error:{exc.__class__.__name__}:{str(exc)[:200]}",
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
                        url=url,
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
                data=merged if merged.page_role in ("listing", "hub") else None,
                fetch_backend=fetch_backend,
                duration_ms=duration_ms,
                is_empty=not bool(merged.title),
                raw_html=raw_debug,
                page_role=merged.page_role,
            )

        extracted_fields: list[str] = []
        missing_fields: list[str] = []
        for field_name in ["title", "price", "currency", "image_url", "description"]:
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
            page_role=merged.page_role,
        )

    async def fetch_html(
        self, url: str, requires_js: bool = False, *, scrape_tier: int = 1
    ) -> str | None:
        """Fetch raw HTML via fetch backends (discovery uses fetch_adapter)."""
        backend_ids = self._layer_order(requires_js=requires_js, scrape_tier=scrape_tier, url=url)
        for backend_id in backend_ids:
            html, _err = await self._fetch_layer_with_retries(backend_id, url)
            if html:
                return html
        return None

    async def _fetch_raw(
        self,
        url: str,
        requires_js: bool = False,
        *,
        scrape_tier: int = 1,
        accept_language: str | None = None,
    ) -> str | None:
        """Fetch and return raw HTML/text for a URL without extraction.

        Tries fetch backends in priority order. Returns None on total failure.
        """
        backend_ids = self._layer_order(requires_js=requires_js, scrape_tier=scrape_tier, url=url)
        for backend_id in backend_ids:
            try:
                html, _err = await self._fetch_layer_with_retries(
                    backend_id,
                    url,
                    accept_language=accept_language,
                )
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
        accept_language: str | None = None,
    ) -> str | None:
        """Lightweight fetch for static documents (sitemap, robots, category/listing pages).

        Order: direct HTTP (fast, free) -> proxy provider without JS render.
        Browser render is intentionally excluded: static content does not need a browser,
        and if both direct HTTP and proxy-provider bypass fail, the document is likely
        unavailable rather than JS-gated.
        """
        html, _err = await self._fetch_static_with_error(
            url, log_url_hint=log_url_hint, accept_language=accept_language
        )
        return html

    async def _fetch_static_with_error(
        self,
        url: str,
        *,
        log_url_hint: str | None = None,
        accept_language: str | None = None,
    ) -> tuple[str | None, str | None]:
        """_fetch_static plus the LAST backend's error, so a caller can tell a
        budget skip (nothing was fetched, retry later) from a missing document."""
        started = time.perf_counter()
        last_err: str | None = None
        for backend_id, render_js in (
            (BackendId.DIRECT_HTTP, None),
            (BackendId.PROXY_PROVIDER, False),
        ):
            backend_started = time.perf_counter()
            html, backend_err = await self._fetch_layer_with_retries(
                backend_id,
                url,
                render_js=render_js,
                accept_language=accept_language,
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
                return html, None
            last_err = backend_err
        total_ms = int((time.perf_counter() - started) * 1000)
        logger.info(
            "fetch_static_failed duration_ms=%s url=%s",
            total_ms,
            (log_url_hint or url)[:200],
        )
        return None, last_err

    @staticmethod
    def _looks_like_sitemap_xml(content: str) -> bool:
        """True when body is XML sitemap / index, not an HTML error page."""
        head = (content or "").lstrip()[:800].lower()
        return head.startswith("<?xml") or "<urlset" in head or "<sitemapindex" in head

    async def _fetch_sitemap_document(self, sitemap_url: str, *, log_hint: str) -> str | None:
        """Fetch sitemap XML via static backends, then browser render as fallback.

        Raises ProxyBudgetExhausted when the paid layer was skipped by the
        budget guard: the document is not missing, the walk must resume when
        the allowance is back (the render fallback is paid too, so it is not
        tried either).
        """
        content, err = await self._fetch_static_with_error(sitemap_url, log_url_hint=log_hint)
        if content and self._looks_like_sitemap_xml(content):
            return content
        if err in PROXY_PROVIDER_SKIP_ERRORS:
            raise ProxyBudgetExhausted(sitemap_url, err)
        html = await self._fetch_raw(sitemap_url, requires_js=True)
        if html and self._looks_like_sitemap_xml(html):
            logger.info(
                "sitemap_fetch_rendered_fallback url=%s",
                sitemap_url[:120],
            )
            return html
        return None

    async def resolve_sitemap_shards(self, base_url: str) -> dict:
        """Resolve the sitemap tree's FIRST level for enumeration fan-out.

        Returns {"shards": [nested sitemap urls...], "entry": <url|None>}
        where shards are the sub-sitemaps of the first index document that
        parses. An empty shard list means the entry document carries URL
        entries directly (no useful fan-out seam).
        """
        from urllib.parse import urljoin

        from app.modules.scraper.extractors import parse_sitemap_xml

        candidates: list[str] = []
        robots_url = urljoin(base_url, "/robots.txt")
        try:
            robots_text = await self._fetch_static(
                robots_url, log_url_hint=f"{base_url} robots.txt"
            )
            if robots_text:
                for line in robots_text.splitlines():
                    line = line.strip()
                    if line.lower().startswith("sitemap:"):
                        ref = line.split(":", 1)[1].strip()
                        if ref:
                            candidates.append(ref)
        except Exception:
            pass
        for path in ("/sitemap.xml", "/sitemap_index.xml", "/sitemap/sitemap.xml"):
            candidate = urljoin(base_url, path)
            if candidate not in candidates:
                candidates.append(candidate)

        for entry in candidates:
            try:
                content = await self._fetch_sitemap_document(
                    entry, log_hint=f"{base_url} sitemap index"
                )
            except ProxyBudgetExhausted:
                raise
            except Exception:
                continue
            if not content:
                continue
            parsed = parse_sitemap_xml(content, base_url)
            nested = [u for u in parsed.get("sitemaps", []) if u]
            if nested or parsed.get("url_entries"):
                return {"shards": nested, "entry": entry}
        return {"shards": [], "entry": None}

    async def fetch_sitemap_candidates(
        self,
        base_url: str,
        *,
        marketplace_locale: str | None = None,
        max_subfiles: int | None = None,
        max_urls: int | None = None,
        with_shard_origin: bool = False,
        explicit_sitemaps: list[str] | None = None,
        lastmod_out: dict[str, str] | None = None,
    ) -> list[str] | list[tuple[str, str]]:
        """Discover sitemap URLs with locale selection and canonical deduplication.

        ``lastmod_out``, when given, collects each selected URL's <lastmod>
        text (harvest optimisation #6 — the shop's own change signal).

        ``max_subfiles`` / ``max_urls`` override the module defaults for the
        sitemap-full onboarding path (quotas are floors, not ceilings); the
        legacy discovery phase keeps the conservative defaults.
        """
        from urllib.parse import urljoin

        from app.modules.scraper.extractors import (
            SITEMAP_MAX_SUBFILES,
            SITEMAP_MAX_URLS,
            parse_sitemap_xml,
        )
        from app.modules.scraper.locale_selection import select_locale_url

        subfile_cap = max_subfiles if max_subfiles is not None else SITEMAP_MAX_SUBFILES
        url_cap = max_urls if max_urls is not None else SITEMAP_MAX_URLS

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

        product_urls: list = []
        seen_hashes: set[str] = set()
        from app.models.facts import FactListing

        visited_sitemaps: set[str] = set()
        # Fan-out shards walk ONLY their assigned subtree (nested indexes
        # under a shard are still followed).
        pending_sitemaps: list[str] = (
            list(explicit_sitemaps)
            if explicit_sitemaps is not None
            else list(sitemap_urls_to_try)
        )

        while pending_sitemaps and len(visited_sitemaps) < subfile_cap:
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
            pending_sitemaps.sort(key=_sitemap_shard_priority)
            for entry in parsed.get("url_entries", []):
                if len(product_urls) >= url_cap:
                    break
                loc = str(entry.get("loc") or "")
                if not loc:
                    continue
                alternates = entry.get("alternates")
                alt_map = alternates if isinstance(alternates, dict) else {}
                selected = select_locale_url(loc, alt_map, marketplace_locale)
                url_hash = FactListing.compute_url_hash(selected)
                if url_hash in seen_hashes:
                    continue
                seen_hashes.add(url_hash)
                if lastmod_out is not None and entry.get("lastmod"):
                    lastmod_out[selected] = str(entry["lastmod"])
                if with_shard_origin:
                    product_urls.append((selected, sitemap_url))
                else:
                    product_urls.append(selected)
            if len(product_urls) >= url_cap:
                break

        return product_urls

    async def walk_sitemaps(
        self,
        base_url: str,
        *,
        explicit_sitemaps: list[str] | None = None,
        max_subfiles: int | None = None,
        prefetch: int = 3,
        subfile_selector: Callable[[list[str]], list[str]] | None = None,
    ):
        """Stream (sitemap_url, parsed) per document with bounded prefetch.

        The enumerator used to fetch the WHOLE tree first (fetch_sitemap_candidates)
        and only then classify/write; this generator lets parsing, dedupe
        and the gate writes of document N overlap the fetch of document N+1
        (2026-09-19 enumeration optimisation #5). Nested indexes found in a
        document are queued behind the current pending list, product-named
        shards first. `prefetch` documents are in flight at once — the
        host throttle still spaces same-host requests. `subfile_selector`
        sees every list of sub-sitemaps before it is queued (the explicit
        list and each index document's children) and returns the ones to
        walk — the multi-locale / media filter of sitemap_locale.
        """
        from urllib.parse import urljoin

        from app.modules.scraper.extractors import SITEMAP_MAX_SUBFILES, parse_sitemap_xml

        subfile_cap = max_subfiles if max_subfiles is not None else SITEMAP_MAX_SUBFILES
        if explicit_sitemaps is not None:
            pending: list[str] = list(explicit_sitemaps)
            if subfile_selector is not None:
                pending = list(subfile_selector(pending))
        else:
            pending = []
            robots_url = urljoin(base_url, "/robots.txt")
            try:
                robots_text = await self._fetch_static(
                    robots_url, log_url_hint=f"{base_url} robots.txt"
                )
                if robots_text:
                    for line in robots_text.splitlines():
                        line = line.strip()
                        if line.lower().startswith("sitemap:"):
                            ref = line.split(":", 1)[1].strip()
                            if ref:
                                pending.append(ref)
            except Exception:
                pass
            for path in ("/sitemap.xml", "/sitemap_index.xml", "/sitemap/sitemap.xml"):
                candidate = urljoin(base_url, path)
                if candidate not in pending:
                    pending.append(candidate)

        visited: set[str] = set()
        in_flight: dict[str, asyncio.Task] = {}

        async def _fetch(url: str) -> str | None:
            try:
                return await self._fetch_sitemap_document(url, log_hint=f"{base_url} sitemap")
            except ProxyBudgetExhausted:
                raise
            except Exception:
                return None

        while (pending or in_flight) and len(visited) < subfile_cap:
            while (
                pending
                and len(in_flight) < prefetch
                and len(visited) + len(in_flight) < subfile_cap
            ):
                url = pending.pop(0)
                if url in visited or url in in_flight:
                    continue
                in_flight[url] = asyncio.create_task(_fetch(url))
            if not in_flight:
                break
            # Yield documents in dispatch order: the oldest in-flight first.
            url, task = next(iter(in_flight.items()))
            content = await task
            del in_flight[url]
            visited.add(url)
            if not content:
                continue
            parsed = parse_sitemap_xml(content, base_url)
            children = list(parsed["sitemaps"])
            if children and subfile_selector is not None:
                children = list(subfile_selector(children))
            for nested in children:
                if nested not in visited and nested not in in_flight:
                    pending.append(nested)
            pending.sort(key=_sitemap_shard_priority)
            yield url, parsed

    async def scrape_page_for_analysis(
        self,
        url: str,
        requires_js: bool = False,
        *,
        static_fetch: bool = False,
        scrape_tier: int = 1,
        accept_language: str | None = None,
    ) -> tuple[str | None, BeautifulSoup | None]:
        """Fetch a page and return (html, soup) for structural analysis.

        Returns (None, None) on failure.
        """
        try:
            if static_fetch:
                html = await self._fetch_static(url, accept_language=accept_language)
            else:
                html = await self._fetch_raw(
                    url,
                    requires_js=requires_js,
                    scrape_tier=scrape_tier,
                    accept_language=accept_language,
                )
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
        backend_ids = self._layer_order(requires_js=requires_js, url=url)
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
        render_js: bool | None = None,
        deadline_monotonic: float | None = None,
        accept_language: str | None = None,
    ) -> tuple[str | None, str | None]:
        """Try backend up to FETCH_ATTEMPTS_PER_LAYER times; return (html, last_error_code)."""
        last_code: str | None = None
        attempts = (
            PAID_BACKEND_ATTEMPTS
            if backend_id == BackendId.PROXY_PROVIDER
            else FETCH_ATTEMPTS_PER_LAYER
        )
        for attempt in range(attempts):
            html, err = await self._fetch_by_backend_once(
                backend_id,
                url,
                render_js=render_js,
                deadline_monotonic=deadline_monotonic,
                accept_language=accept_language,
            )
            if html:
                return html, None
            last_code = err or "fetch_failed"
            if last_code in _NON_RETRIABLE_LAYER_ERRORS:
                break
            if last_code in PROXY_PROVIDER_SKIP_ERRORS:
                break
            if attempt < attempts - 1:
                await asyncio.sleep(RETRY_BACKOFF_SEC * (attempt + 1))
        mapped = self._map_layer_error(last_code, backend_id)
        if last_code in PROXY_PROVIDER_SKIP_ERRORS:
            return None, last_code
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
        render_js: bool | None = None,
        deadline_monotonic: float | None = None,
        accept_language: str | None = None,
    ) -> tuple[str | None, str | None]:
        backend = get_fetch_backend(backend_id)
        if backend_id == BackendId.PROXY_PROVIDER:
            # JS rendering costs 2.2x the proxy credits (Decodo $49 plan:
            # $0.65 vs $0.30 per 1k). None = the marketplace's access_mode
            # decides; an explicit False (static documents, list pages proven
            # server-rendered) is honoured — until 2026-09-19 the policy
            # overrode it and every sitemap of a proxy_render shop was billed
            # at the JS tier.
            if render_js is None:
                render_js = access_policy.wants_proxy_render(url)
        elif render_js is None:
            render_js = True
        await host_throttle.acquire(url)
        return await backend.fetch(
            url,
            render_js=render_js,
            deadline_monotonic=deadline_monotonic,
            accept_language=accept_language,
        )

    def _layer_order(
        self,
        requires_js: bool,
        scrape_tier: int = 1,
        url: str | None = None,
    ) -> list[BackendId]:
        """Return the ordered list of fetch backends to try for one scrape attempt.

        Backend order is determined by the marketplace's access_mode (resolved
        per URL host via access_policy; scrape/discovery register it when they
        load the marketplace row) with requires_js kept as a legacy render hint
        inside direct mode:

            direct        direct_http -> browser_render
            render        browser_render -> direct_http (requires_js implies this)
            proxy         proxy_provider only
            proxy_render  proxy_provider only (JS rendering requested)

        The paid proxy backend participates ONLY in proxy modes: quota is never
        spent escalating a direct-mode shop — a blocked shop fails honestly and
        gets its access_mode raised instead. A proxy-mode shop with the proxy
        unconfigured returns [] (fetch fails, alerts fire; nothing silently
        downgrades to a datacenter fetch that is known to be blocked).

        Tier 2 / Tier 3 remain documented placeholders in _SUPPORTED_SCRAPE_TIERS.
        Raises NotImplementedError / ValueError for unsupported / unknown tiers.
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

        mode = access_policy.mode_for(url)
        if mode in (access_policy.MODE_PROXY, access_policy.MODE_PROXY_RENDER):
            if ProxyProviderBackend.is_configured():
                return [BackendId.PROXY_PROVIDER]
            # A proxy-mode host with no configured provider must NOT fail
            # silently: every fetch would be skipped and a whole discovery
            # budget burned with zero requests (barbora probe, 2026-09-16).
            emit_ops_alert(
                module="scraper",
                submodule="proxy",
                severity="error",
                anomaly_type="proxy_unconfigured",
                message=(
                    "Host requires proxy access but the proxy provider is not "
                    "configured (set DECODO_API_URL/USERNAME/PASSWORD and "
                    "DECODO_ENABLED=true on the worker service); all fetches "
                    "for this host are skipped"
                ),
                entity=urlparse(url).netloc if url else "",
                context={"mode": mode, "host": urlparse(url).netloc if url else None},
            )
            return []
        if mode == access_policy.MODE_RENDER or requires_js:
            return [BackendId.BROWSER_RENDER, BackendId.DIRECT_HTTP]
        return [BackendId.DIRECT_HTTP, BackendId.BROWSER_RENDER]

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
