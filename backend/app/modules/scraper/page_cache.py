"""Redis TTL cache for fetched PDP HTML (transient content, bypasses the gate).

Discovery classifies every candidate URL by fetching it; the pipeline's scrape
phase used to re-fetch the same page minutes later — twice the traffic and
time on every fresh shop. Product pages classified during discovery are cached
(zlib-compressed, keyed by url_hash) so the first scrape touch is free.

TTL is short by design: it bridges discovery -> first scrape inside one
pipeline run and must never serve stale prices to the recurring 6h re-scrape.
Best-effort throughout: any Redis failure degrades to a normal network fetch.
"""

from __future__ import annotations

import logging
import zlib
from typing import Any

from app.config import Settings
from app.models.facts import FactListing

logger = logging.getLogger(__name__)

PAGE_CACHE_TTL_SEC = 1800
_MAX_COMPRESSED_BYTES = 200_000
_KEY_PREFIX = "pagecache:"

_redis_client: Any | None = None


def _get_redis() -> Any:
    """Lazy binary-safe Redis client (news/cache.py pattern, bytes payloads)."""
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    import redis

    settings = Settings()
    _redis_client = redis.from_url(settings.redis_url, decode_responses=False)
    return _redis_client


def _key(url: str) -> str:
    return _KEY_PREFIX + FactListing.compute_url_hash(url)


def put_html(url: str, html: str) -> None:
    """Best-effort cache write; oversized pages and Redis errors are skipped."""
    if not html:
        return
    try:
        payload = zlib.compress(html.encode("utf-8"), level=6)
    except Exception:
        return
    if len(payload) > _MAX_COMPRESSED_BYTES:
        return
    try:
        _get_redis().setex(_key(url), PAGE_CACHE_TTL_SEC, payload)
    except Exception as exc:
        logger.debug("page_cache_put_failed url=%s err=%s", url[:120], exc)


def get_html(url: str) -> str | None:
    """Return cached HTML or None on miss / Redis failure; hit deletes the key
    (single-consumer bridge — the scrape touch that follows discovery)."""
    try:
        client = _get_redis()
        key = _key(url)
        raw = client.get(key)
        if raw:
            client.delete(key)
    except Exception as exc:
        logger.debug("page_cache_get_failed url=%s err=%s", url[:120], exc)
        return None
    if not raw:
        return None
    try:
        return zlib.decompress(raw).decode("utf-8")
    except Exception:
        return None
