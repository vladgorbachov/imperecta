"""Category pages harvested from sitemaps (2026-09-19, harvest optimisation #3).

The sitemap enumerator kept only product-like URLs; the category/listing
URLs in the same files were dropped. Those are exactly the pages the list
harvester needs, and a sitemap file costs one request where a BFS category
recon costs hundreds (paid, for the proxy-mode shops). This module turns
the enumerator's raw URL stream into `dim_marketplace.discovered_category_urls`
entries — merged with what discovery already found, never replacing it.
"""

from __future__ import annotations

from urllib.parse import urlparse

from app.modules.scraper.extractors import _has_path_facet, _is_category_url
from app.modules.scraper.scraper_pool import _sitemap_shard_priority

# Site chrome that is never a listing page. Deliberately NOT the extractor's
# _EXCLUDED_LINK_HINTS: that list also drops "catalog"/"category" because it
# hunts product links; here those words are the signal.
_CHROME_HINTS = (
    "login", "signin", "signup", "register", "cart", "basket", "checkout",
    "wishlist", "account", "compare", "help", "faq", "about", "contact",
    "blog", "news", "privacy", "terms", "return", "delivery", "shipping",
    "search", "filter", "sort", "otzyvy", "/reviews", "sitemap",
)

# Shard names that announce category listings (matched with "sitemap"
# stripped, like the product hints in scraper_pool).
CATEGORY_SHARD_HINTS = ("categor", "kategor", "categorie", "collection", "catalog", "katalog")

# Bounds the JSONB column, not the walk: the harvest quota is sized by pool
# size, so the category count only decides how long one pass is. 2,000 URLs
# is ~160 KB in the row, which every harvest run loads.
SITEMAP_CATEGORY_URLS_MAX = 2000


def is_category_shard(shard_url: str | None) -> bool:
    if not shard_url:
        return False
    name = shard_url.lower().rsplit("/", 1)[-1].replace("sitemap", "")
    return any(hint in name for hint in CATEGORY_SHARD_HINTS)


def category_like(url: str) -> bool:
    """Structural test: a listing page, not a product, not chrome/facets."""
    from app.common import html_parsing as _hp

    if _hp._use_rust():
        return _hp._rust_core.category_like_url(url)
    parsed = urlparse(url)
    path = parsed.path or "/"
    if path == "/" or parsed.query:
        return False
    if _has_path_facet(path):
        return False
    lowered = path.lower()
    if any(hint in lowered for hint in _CHROME_HINTS):
        return False
    return _is_category_url(path)


def collect_category_urls(entries: list[tuple[str, str | None]], base_host: str) -> list[str]:
    """Category-like URLs from (url, shard_url) sitemap entries, same host only.

    URLs from category-named shards come first (stable), then structural
    finds from neutral shards; deduped, capped.
    """
    from_shards: list[str] = []
    structural: list[str] = []
    seen: set[str] = set()
    for url, shard in entries:
        # A product-named shard lists products by the shop's own word.
        if shard and _sitemap_shard_priority(shard) == 0 and not is_category_shard(shard):
            continue
        host = urlparse(url).netloc.lower().removeprefix("www.")
        if host != base_host or url in seen or not category_like(url):
            continue
        seen.add(url)
        (from_shards if is_category_shard(shard) else structural).append(url)
    return (from_shards + structural)[:SITEMAP_CATEGORY_URLS_MAX]


def merge_category_urls(existing: object, found: list[str]) -> list[str]:
    """Existing discovery results stay first; new sitemap finds append."""
    current = [u for u in existing if isinstance(u, str)] if isinstance(existing, list) else []
    seen = set(current)
    merged = list(current)
    for url in found:
        if url not in seen:
            seen.add(url)
            merged.append(url)
    return merged[:SITEMAP_CATEGORY_URLS_MAX]


async def publish_category_urls(marketplace, found: list[str]) -> int:
    """Merge `found` into the shop's discovered_category_urls via the META door.

    Returns how many URLs were new. A no-op when nothing is new.
    """
    if not found:
        return 0
    from app.modules.persist.meta_write import (
        build_dim_marketplace_fields,
        write_meta_async,
    )

    existing = getattr(marketplace, "discovered_category_urls", None)
    merged = merge_category_urls(existing, found)
    current_len = len(existing) if isinstance(existing, list) else 0
    added = len(merged) - current_len
    if added <= 0:
        return 0
    await write_meta_async(
        table="dim_marketplace",
        operation="update",
        fields=build_dim_marketplace_fields(
            id=marketplace.id,
            discovered_category_urls=merged,
        ),
        reject_source="sitemap_categories",
    )
    return added

