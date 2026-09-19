"""Vendor-neutral fetch backend identifiers and implementations."""

from __future__ import annotations

import asyncio
import atexit
import base64
import hashlib
import logging
import threading
import weakref
from enum import Enum
from typing import ClassVar, Protocol
from urllib.parse import urlparse

import httpx
from playwright.async_api import async_playwright

from app.config import Settings
from app.modules.scraper.proxy_provider_limiter import (
    PROXY_PROVIDER_DEADLINE_ERROR,
    acquire_proxy_provider_token,
)

logger = logging.getLogger(__name__)
settings = Settings()

HTTP_TIMEOUT_SEC = 25.0
PROXY_PROVIDER_TIMEOUT_SEC = 60.0
PLAYWRIGHT_GOTO_TIMEOUT_MS = 35_000
PLAYWRIGHT_WAIT_MS = 2_500
# Small pool of current desktop browser identities. The pick is stable per
# HOST (hash of netloc), so one shop always sees one consistent browser —
# rotating per request is a stronger bot signal than a fixed identity.
_USER_AGENT_POOL: tuple[str, ...] = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) "
    "Gecko/20100101 Firefox/133.0",
)
_DEFAULT_USER_AGENT = _USER_AGENT_POOL[0]

_ACCEPT_HTML = (
    "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,"
    "image/webp,*/*;q=0.8"
)

_DEFAULT_ACCEPT_LANGUAGE = "en, en-US;q=0.9"


def _user_agent_for(url: str | None) -> str:
    """Stable per-host identity from the UA pool."""
    if not url:
        return _DEFAULT_USER_AGENT
    host = urlparse(url).netloc.lower()
    if not host:
        return _DEFAULT_USER_AGENT
    digest = hashlib.sha256(host.encode("utf-8")).digest()
    return _USER_AGENT_POOL[digest[0] % len(_USER_AGENT_POOL)]


def _request_headers(accept_language: str | None = None, url: str | None = None) -> dict[str, str]:
    return {
        "User-Agent": _user_agent_for(url),
        "Accept": _ACCEPT_HTML,
        "Accept-Language": accept_language or _DEFAULT_ACCEPT_LANGUAGE,
    }


class BackendId(str, Enum):
    """Neutral fetch-backend identifiers persisted to scrape_logs.scraper_type."""

    DIRECT_HTTP = "direct_http"
    PROXY_PROVIDER = "proxy_provider"
    BROWSER_RENDER = "browser_render"
    # Not a network backend: HTML bridged from the discovery classify fetch
    # via page_cache; never appears in _layer_order / _BACKENDS.
    PAGE_CACHE = "page_cache"


LEGACY_LAYER_TO_BACKEND: dict[str, BackendId] = {
    "httpx": BackendId.DIRECT_HTTP,
    "decodo": BackendId.PROXY_PROVIDER,
    "decodo_static": BackendId.PROXY_PROVIDER,
    "playwright": BackendId.BROWSER_RENDER,
}

ALL_LEGACY_LAYER_STRINGS = frozenset(LEGACY_LAYER_TO_BACKEND.keys())


def backend_id_persisted(backend_id: BackendId | None) -> str | None:
    """Value written to scrape_logs.scraper_type (collapses static proxy to proxy_provider)."""
    if backend_id is None:
        return None
    return backend_id.value


def legacy_layer_to_backend_id(layer: str | None) -> BackendId | None:
    """Map a legacy layer string to exactly one BackendId."""
    if layer is None:
        return None
    return LEGACY_LAYER_TO_BACKEND.get(layer)


class FetchBackend(Protocol):
    """Async HTML fetch for one backend."""

    backend_id: ClassVar[BackendId]

    async def fetch(
        self,
        url: str,
        *,
        render_js: bool = True,
        deadline_monotonic: float | None = None,
        accept_language: str | None = None,
    ) -> tuple[str | None, str | None]:
        """Return (html, error_code). error_code is None on success."""


# One keep-alive client per running event loop: connection/TLS reuse across
# the thousands of same-host fetches a scrape or discovery job performs.
# Celery tasks each run a fresh loop, so clients are cached per loop; a dead
# loop's entry is dropped by the weak reference together with its sockets.
_loop_http_clients: "weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, httpx.AsyncClient]" = (
    weakref.WeakKeyDictionary()
)


def _shared_http_client() -> httpx.AsyncClient:
    loop = asyncio.get_running_loop()
    client = _loop_http_clients.get(loop)
    if client is None or client.is_closed:
        client = httpx.AsyncClient(
            timeout=httpx.Timeout(HTTP_TIMEOUT_SEC),
            follow_redirects=True,
            http2=True,
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
        )
        _loop_http_clients[loop] = client
    return client


class DirectHttpBackend:
    """Direct HTTP GET without a proxy provider or browser."""

    backend_id = BackendId.DIRECT_HTTP

    async def fetch(
        self,
        url: str,
        *,
        render_js: bool = True,
        deadline_monotonic: float | None = None,
        accept_language: str | None = None,
    ) -> tuple[str | None, str | None]:
        del render_js, deadline_monotonic
        headers = _request_headers(accept_language, url=url)
        try:
            client = _shared_http_client()
            response = await client.get(url, headers=headers)
            if response.status_code == 404:
                return None, "not_found"
            if response.status_code in (403, 401):
                return None, "blocked"
            if response.status_code >= 400:
                return None, "fetch_failed"
            return response.text, None
        except httpx.TimeoutException:
            logger.warning("direct_http timeout for %s", url[:120])
            return None, "timeout"
        except httpx.HTTPStatusError as exc:
            logger.warning("direct_http HTTP error for %s: %s", url[:120], exc)
            return None, "fetch_failed"
        except Exception as exc:
            logger.warning("direct_http fetch failed for %s: %s", url[:120], exc)
            return None, "fetch_failed"


class ProxyProviderBackend:
    """Remote proxy-provider API fetch (credentials from neutral settings)."""

    backend_id = BackendId.PROXY_PROVIDER

    @staticmethod
    def is_configured() -> bool:
        return bool(
            settings.proxy_provider_enabled
            and settings.proxy_provider_username
            and settings.proxy_provider_password
        )

    @staticmethod
    def is_enabled() -> bool:
        return bool(settings.proxy_provider_enabled)

    @staticmethod
    def api_url() -> str:
        return settings.proxy_provider_api_url or ""

    async def fetch(
        self,
        url: str,
        *,
        render_js: bool = True,
        deadline_monotonic: float | None = None,
        accept_language: str | None = None,
    ) -> tuple[str | None, str | None]:
        if not settings.proxy_provider_enabled:
            return None, "fetch_failed"
        if not (settings.proxy_provider_username and settings.proxy_provider_password):
            logger.debug("Proxy provider credentials not configured, skipping")
            return None, "fetch_failed"
        if not await acquire_proxy_provider_token(deadline_monotonic):
            return None, PROXY_PROVIDER_DEADLINE_ERROR
        auth = base64.b64encode(
            f"{settings.proxy_provider_username}:{settings.proxy_provider_password}".encode()
        ).decode()
        api_url = f"{settings.proxy_provider_api_url.rstrip('/')}/scrape"
        payload: dict[str, str] = {"url": url}
        if render_js:
            payload["headless"] = "html"
        if accept_language:
            payload["Accept-Language"] = accept_language
        timeout = httpx.Timeout(PROXY_PROVIDER_TIMEOUT_SEC)
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
            logger.warning("proxy_provider timeout for %s", url[:120])
            return None, "timeout"
        except httpx.HTTPStatusError as exc:
            logger.warning("proxy_provider HTTP error for %s: %s", url[:120], exc)
            return None, "fetch_failed"
        except Exception as exc:
            logger.warning("proxy_provider fetch failed for %s: %s", url[:120], exc)
            return None, "fetch_failed"


# Reusable headless browser per event loop: chromium launch costs seconds and
# real CPU, so one job launches once and renders many pages. The browser is
# recycled after RENDER_PAGES_PER_BROWSER fetches (memory hygiene) and dropped
# on any launch/render infrastructure failure.
# 40 -> 12 after the 2026-09-16 full run: worker pool processes died with
# SIGKILL (OOM) once render-heavy shops queued up; a long-lived Chromium
# accretes memory and the container has no headroom for it.
RENDER_PAGES_PER_BROWSER = 12

# One long-lived event loop per PROCESS for all Playwright work. Celery tasks
# execute coroutines on one-shot asyncio.run() loops, so keying browser reuse
# on the CALLER's loop meant a fresh Chromium launch on every fetch — and,
# because the success path never closes the holder, an orphaned Chromium+Node
# pair leaked per completed render (2026-09-19 incident: fork_exec
# BlockingIOError storms once the container process table filled). Pinning all
# renders to this thread makes the holder cache, the RENDER_PAGES_PER_BROWSER
# rotation and the one-render-at-a-time semaphore hold process-wide.
_render_loop_lock = threading.Lock()
_render_loop_singleton: asyncio.AbstractEventLoop | None = None


def _shutdown_render_loop(loop: asyncio.AbstractEventLoop) -> None:
    """Best-effort browser close when a worker child exits/recycles."""

    async def _close_holder() -> None:
        holder = _loop_browsers.get(loop)
        if holder is not None:
            await holder.close()

    try:
        asyncio.run_coroutine_threadsafe(_close_holder(), loop).result(timeout=10)
    except Exception:
        pass
    try:
        loop.call_soon_threadsafe(loop.stop)
    except Exception:
        pass


def _get_render_loop() -> asyncio.AbstractEventLoop:
    global _render_loop_singleton
    with _render_loop_lock:
        loop = _render_loop_singleton
        if loop is None or loop.is_closed():
            loop = asyncio.new_event_loop()
            threading.Thread(
                target=loop.run_forever,
                name="playwright-render-loop",
                daemon=True,
            ).start()
            atexit.register(_shutdown_render_loop, loop)
            _render_loop_singleton = loop
        return loop


# At most ONE in-flight render per process: a second concurrent Chromium
# page is exactly the peak that OOM-killed the worker. Direct/proxy fetches
# are unaffected. (The semaphore lives on the render loop, so it is a real
# process-wide limit, not per-caller-loop.)
_loop_render_semaphores: (
    "weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, asyncio.Semaphore]"
) = weakref.WeakKeyDictionary()


def _render_semaphore() -> asyncio.Semaphore:
    loop = asyncio.get_running_loop()
    sem = _loop_render_semaphores.get(loop)
    if sem is None:
        sem = asyncio.Semaphore(1)
        _loop_render_semaphores[loop] = sem
    return sem


class _BrowserHolder:
    def __init__(self) -> None:
        self.playwright = None
        self.browser = None
        self.pages_served = 0

    async def close(self) -> None:
        try:
            if self.browser is not None:
                await self.browser.close()
        except Exception:
            pass
        try:
            if self.playwright is not None:
                await self.playwright.stop()
        except Exception:
            pass
        self.playwright = None
        self.browser = None
        self.pages_served = 0


_loop_browsers: "weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, _BrowserHolder]" = (
    weakref.WeakKeyDictionary()
)


async def _shared_browser() -> "_BrowserHolder":
    loop = asyncio.get_running_loop()
    holder = _loop_browsers.get(loop)
    if holder is None:
        holder = _BrowserHolder()
        _loop_browsers[loop] = holder
    if holder.browser is not None and holder.pages_served >= RENDER_PAGES_PER_BROWSER:
        await holder.close()
    if holder.browser is None or not holder.browser.is_connected():
        await holder.close()
        holder.playwright = await async_playwright().start()
        holder.browser = await holder.playwright.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-extensions",
                # We parse DOM, not pixels: skipping image decode cuts the
                # biggest chunk of renderer memory and bandwidth.
                "--blink-settings=imagesEnabled=false",
            ],
        )
    return holder


class BrowserRenderBackend:
    """Headless browser render fetch (shared browser, fresh context per page)."""

    backend_id = BackendId.BROWSER_RENDER

    async def fetch(
        self,
        url: str,
        *,
        render_js: bool = True,
        deadline_monotonic: float | None = None,
        accept_language: str | None = None,
    ) -> tuple[str | None, str | None]:
        del render_js, deadline_monotonic
        future = asyncio.run_coroutine_threadsafe(
            self._fetch_on_render_loop(url, accept_language),
            _get_render_loop(),
        )
        return await asyncio.wrap_future(future)

    async def _fetch_on_render_loop(
        self,
        url: str,
        accept_language: str | None,
    ) -> tuple[str | None, str | None]:
        async with _render_semaphore():
            return await self._fetch_locked(url, accept_language)

    async def _fetch_locked(
        self,
        url: str,
        accept_language: str | None,
    ) -> tuple[str | None, str | None]:
        holder: _BrowserHolder | None = None
        context = None
        try:
            holder = await _shared_browser()
            context = await holder.browser.new_context(
                user_agent=_user_agent_for(url),
                locale=(accept_language.split(",")[0].strip() if accept_language else None),
                extra_http_headers=(
                    {"Accept-Language": accept_language} if accept_language else None
                ),
                viewport={"width": 1920, "height": 1080},
            )
            page = await context.new_page()
            holder.pages_served += 1
            try:
                resp = await page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=PLAYWRIGHT_GOTO_TIMEOUT_MS,
                )
                if resp is not None and resp.status == 404:
                    return None, "not_found"
                if resp is not None and resp.status in (401, 403):
                    return None, "blocked"
            except Exception as exc:
                msg = str(exc).lower()
                if "timeout" in msg or "timed out" in msg:
                    return None, "timeout"
                return None, "fetch_failed"
            await page.wait_for_timeout(PLAYWRIGHT_WAIT_MS)
            html = await page.content()
            return html, None
        except Exception as exc:
            logger.warning("browser_render fetch failed for %s: %s", url[:120], exc)
            if holder is not None:
                await holder.close()
            msg = str(exc).lower()
            if "timeout" in msg or "timed out" in msg:
                return None, "timeout"
            return None, "fetch_failed"
        finally:
            if context is not None:
                try:
                    await context.close()
                except Exception:
                    pass


_BACKENDS: dict[BackendId, FetchBackend] = {
    BackendId.DIRECT_HTTP: DirectHttpBackend(),
    BackendId.PROXY_PROVIDER: ProxyProviderBackend(),
    BackendId.BROWSER_RENDER: BrowserRenderBackend(),
}


def get_fetch_backend(backend_id: BackendId) -> FetchBackend:
    return _BACKENDS[backend_id]
