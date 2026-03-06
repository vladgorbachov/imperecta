"""Decodo (SmartProxy) rotating residential proxy manager."""

import logging
import random
import string
import time
from dataclasses import dataclass
from urllib.parse import urlparse, urlunparse

from app.config import Settings

logger = logging.getLogger(__name__)


@dataclass
class ProxyStats:
    """Track proxy usage and failures."""

    total_requests: int = 0
    successful: int = 0
    failed: int = 0
    last_used: float = 0.0
    consecutive_failures: int = 0


class ProxyManager:
    """
    Manages Decodo (SmartProxy) rotating residential proxies.

    Supports:
    - Rotating mode: new IP every request (default)
    - Sticky sessions: same IP for a configurable duration
    - Geo-targeting: route through specific country
    - Automatic failover and retry logic
    """

    def __init__(self) -> None:
        self.settings = Settings()
        self._stats: dict[str, ProxyStats] = {}
        self._session_cache: dict[str, tuple[str, float]] = {}  # key -> (session_id, created_at)

    @property
    def is_available(self) -> bool:
        """Check if any proxy is configured."""
        return bool(self.settings.proxy_url)

    def get_proxy(
        self,
        country: str | None = None,
        sticky_key: str | None = None,
    ) -> dict[str, str] | None:
        """
        Get proxy config dict for httpx/playwright.

        Args:
            country: ISO 2-letter code for geo-targeting (e.g. "DE", "PL").
                     Adds -country-xx suffix to Decodo username.
            sticky_key: Unique key for sticky session (e.g. "marketplace_id:product_id").
                        Same key = same IP for proxy_sticky_duration minutes.

        Returns:
            Dict {"http": proxy_url, "https": proxy_url} or None if no proxy configured.
        """
        base_url = self.settings.proxy_url
        if not base_url:
            return None

        proxy_url = self._build_proxy_url(base_url, country, sticky_key)

        # Track usage
        stats = self._stats.setdefault(proxy_url, ProxyStats())
        stats.total_requests += 1
        stats.last_used = time.time()

        logger.debug(
            "Proxy assigned: country=%s, sticky=%s, url=%s",
            country,
            bool(sticky_key),
            self._mask_url(proxy_url),
        )

        return {"http": proxy_url, "https": proxy_url}

    def get_playwright_proxy(
        self,
        country: str | None = None,
        sticky_key: str | None = None,
    ) -> dict | None:
        """
        Get proxy config dict for Playwright browser.

        Returns:
            Dict {"server": "http://host:port", "username": "user", "password": "pass"}
            or None if no proxy configured.
        """
        base_url = self.settings.proxy_url
        if not base_url:
            return None

        proxy_url = self._build_proxy_url(base_url, country, sticky_key)
        parsed = urlparse(proxy_url)

        return {
            "server": f"{parsed.scheme}://{parsed.hostname}:{parsed.port}",
            "username": parsed.username or "",
            "password": parsed.password or "",
        }

    def report_success(self, proxy_url: str | None = None) -> None:
        """Report successful request through proxy."""
        url = proxy_url or self.settings.proxy_url
        if url and url in self._stats:
            self._stats[url].successful += 1
            self._stats[url].consecutive_failures = 0

    def report_failure(self, proxy_url: str | None = None) -> None:
        """Report failed request through proxy."""
        url = proxy_url or self.settings.proxy_url
        if url and url in self._stats:
            self._stats[url].failed += 1
            self._stats[url].consecutive_failures += 1

    def get_stats(self) -> dict:
        """Get proxy usage statistics."""
        if not self._stats:
            return {"configured": self.is_available, "stats": {}}
        return {
            "configured": self.is_available,
            "stats": {
                self._mask_url(k): {
                    "total": v.total_requests,
                    "successful": v.successful,
                    "failed": v.failed,
                    "success_rate": (
                        round(v.successful / v.total_requests * 100, 1)
                        if v.total_requests > 0
                        else 0
                    ),
                    "consecutive_failures": v.consecutive_failures,
                }
                for k, v in self._stats.items()
            },
        }

    def _build_proxy_url(
        self,
        base_url: str,
        country: str | None,
        sticky_key: str | None,
    ) -> str:
        """Build proxy URL with Decodo suffixes for geo/sticky."""
        parsed = urlparse(base_url)
        username = parsed.username or ""

        # Add geo-targeting suffix
        if country and self.settings.proxy_country_routing:
            username = f"{username}-country-{country.lower()}"

        # Add sticky session suffix
        if sticky_key:
            session_id = self._get_or_create_session(sticky_key)
            username = f"{username}-session-{session_id}"

        # Rebuild URL with modified username
        password = parsed.password or ""
        netloc = f"{username}:{password}@{parsed.hostname}:{parsed.port}"
        return urlunparse((parsed.scheme, netloc, parsed.path, "", "", ""))

    def _get_or_create_session(self, key: str) -> str:
        """Get existing sticky session or create new one."""
        now = time.time()
        duration = self.settings.proxy_sticky_duration * 60  # minutes to seconds

        if key in self._session_cache:
            session_id, created_at = self._session_cache[key]
            if now - created_at < duration:
                return session_id

        # Create new session
        session_id = "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
        self._session_cache[key] = (session_id, now)

        # Cleanup old sessions
        self._cleanup_sessions(now, duration)

        return session_id

    def _cleanup_sessions(self, now: float, max_age: float) -> None:
        """Remove expired sticky sessions."""
        expired = [k for k, (_, t) in self._session_cache.items() if now - t > max_age]
        for k in expired:
            del self._session_cache[k]

    @staticmethod
    def _mask_url(url: str) -> str:
        """Mask credentials in URL for logging."""
        parsed = urlparse(url)
        if parsed.username:
            masked = url.replace(parsed.username, "***")
            if parsed.password:
                masked = masked.replace(parsed.password, "***")
            return masked
        return url


# Singleton instance
proxy_manager = ProxyManager()
