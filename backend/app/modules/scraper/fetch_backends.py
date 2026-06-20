"""Vendor-neutral fetch backend identifiers and implementations."""

from __future__ import annotations

import base64
import logging
from enum import Enum
from typing import ClassVar, Protocol

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


class BackendId(str, Enum):
    """Neutral fetch-backend identifiers persisted to scrape_logs.scraper_type."""

    DIRECT_HTTP = "direct_http"
    PROXY_PROVIDER = "proxy_provider"
    BROWSER_RENDER = "browser_render"


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
    ) -> tuple[str | None, str | None]:
        """Return (html, error_code). error_code is None on success."""


class DirectHttpBackend:
    """Direct HTTP GET without a proxy provider or browser."""

    backend_id = BackendId.DIRECT_HTTP

    async def fetch(
        self,
        url: str,
        *,
        render_js: bool = True,
        deadline_monotonic: float | None = None,
    ) -> tuple[str | None, str | None]:
        del render_js, deadline_monotonic
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
            logger.warning("direct_http timeout for %s", url[:120])
            return None, "timeout"
        except httpx.HTTPStatusError as exc:
            logger.warning("direct_http HTTP error for %s: %s", url[:120], exc)
            return None, "fetch_failed"
        except Exception as exc:
            logger.warning("direct_http fetch failed for %s: %s", url[:120], exc)
            return None, "fetch_failed"


class ProxyProviderBackend:
    """Remote proxy-provider API fetch (vendor config read from settings until Stage 2)."""

    backend_id = BackendId.PROXY_PROVIDER

    @staticmethod
    def is_configured() -> bool:
        return bool(
            settings.decodo_enabled
            and settings.decodo_username
            and settings.decodo_password
        )

    @staticmethod
    def is_enabled() -> bool:
        return bool(settings.decodo_enabled)

    @staticmethod
    def api_url() -> str:
        return settings.decodo_api_url

    async def fetch(
        self,
        url: str,
        *,
        render_js: bool = True,
        deadline_monotonic: float | None = None,
    ) -> tuple[str | None, str | None]:
        if not settings.decodo_enabled:
            return None, "fetch_failed"
        if not (settings.decodo_username and settings.decodo_password):
            logger.debug("Proxy provider credentials not configured, skipping")
            return None, "fetch_failed"
        if not await acquire_proxy_provider_token(deadline_monotonic):
            return None, PROXY_PROVIDER_DEADLINE_ERROR
        auth = base64.b64encode(
            f"{settings.decodo_username}:{settings.decodo_password}".encode()
        ).decode()
        api_url = f"{settings.decodo_api_url.rstrip('/')}/scrape"
        payload: dict[str, str] = {"url": url}
        if render_js:
            payload["headless"] = "html"
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


class BrowserRenderBackend:
    """Headless browser render fetch."""

    backend_id = BackendId.BROWSER_RENDER

    async def fetch(
        self,
        url: str,
        *,
        render_js: bool = True,
        deadline_monotonic: float | None = None,
    ) -> tuple[str | None, str | None]:
        del render_js, deadline_monotonic
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
            logger.warning("browser_render fetch failed for %s: %s", url[:120], exc)
            msg = str(exc).lower()
            if "timeout" in msg or "timed out" in msg:
                return None, "timeout"
            return None, "fetch_failed"


_BACKENDS: dict[BackendId, FetchBackend] = {
    BackendId.DIRECT_HTTP: DirectHttpBackend(),
    BackendId.PROXY_PROVIDER: ProxyProviderBackend(),
    BackendId.BROWSER_RENDER: BrowserRenderBackend(),
}


def get_fetch_backend(backend_id: BackendId) -> FetchBackend:
    return _BACKENDS[backend_id]
