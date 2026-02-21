"""Proxy rotation and failure tracking."""

import time
from collections.abc import Iterator

from app.config import Settings

settings = Settings()
FAILURE_COOLDOWN_SEC = 300  # 5 minutes


class ProxyManager:
    """Load proxies from config, round-robin rotation, mark failed for 5 min."""

    def __init__(self) -> None:
        self._proxies: list[str] = [p for p in settings.proxy_list_parsed if p]
        self._index = 0
        self._failed: dict[str, float] = {}

    def get_proxy(self) -> str | None:
        """Get next proxy (round-robin). Returns None if no proxies (work directly for dev)."""
        if not self._proxies:
            return None

        now = time.time()
        self._failed = {p: t for p, t in self._failed.items() if now - t < FAILURE_COOLDOWN_SEC}

        for _ in range(len(self._proxies)):
            proxy = self._proxies[self._index]
            self._index = (self._index + 1) % len(self._proxies)
            if proxy not in self._failed:
                return proxy

        return None

    def mark_failed(self, proxy: str) -> None:
        """Temporarily exclude proxy for 5 minutes."""
        self._failed[proxy] = time.time()
