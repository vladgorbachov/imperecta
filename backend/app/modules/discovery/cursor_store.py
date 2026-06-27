"""Pure storage for discovery cursor/state fields on DimMarketplace."""

from __future__ import annotations

from collections import deque
from collections.abc import Mapping
from datetime import datetime
from typing import Any

from app.models.dimensions import DimMarketplace

DISCOVERY_MP_WRITE_KEYS: tuple[str, ...] = (
    "base_url",
    "last_sitemap_harvest_at",
    "sitemap_url",
    "recon_frontier_state",
    "discovered_category_urls",
    "category_resume_index",
    "sitemap_resume_offset",
    "sitemap_bad_harvest_streak",
    "phase1_exhausted_streak",
    "last_discovery_at",
    "last_discovery_status",
    "last_discovery_products_found",
    "products_in_pool",
    "last_category_recon_at",
)


def load_frontier_state(marketplace: DimMarketplace) -> dict[str, Any] | None:
    """Read raw recon_frontier_state JSONB from the marketplace ORM instance."""
    return marketplace.recon_frontier_state


def parse_frontier(
    saved: Mapping[str, Any],
) -> tuple[deque[tuple[str, int]], set[str], list[str]]:
    """Deserialize frontier JSONB into runtime BFS structures."""
    queue: deque[tuple[str, int]] = deque(
        (str(item[0]), int(item[1]))
        for item in saved.get("queue", [])
    )
    visited: set[str] = set(saved.get("visited", []))
    listing_urls: list[str] = list(saved.get("listing_urls", []))
    return queue, visited, listing_urls


def _cold_start_frontier(
    marketplace: DimMarketplace,
) -> tuple[deque[tuple[str, int]], set[str], list[str]]:
    """Fresh BFS seed — mirrors bfs_walker.run_category_bfs else branch."""
    base_url = marketplace.base_url
    queue: deque[tuple[str, int]] = deque([(base_url, 0)])
    visited: set[str] = {base_url}
    listing_urls: list[str] = []
    return queue, visited, listing_urls


def _frontier_schema_error_kind(saved: Mapping[str, Any]) -> str | None:
    """Return an error_kind when saved frontier JSONB fails structural validation."""
    queue_raw = saved.get("queue")
    if not isinstance(queue_raw, list):
        return "queue_not_list"
    for item in queue_raw:
        if not isinstance(item, (list, tuple)) or len(item) != 2:
            return "queue_item_invalid"
        try:
            int(item[1])
        except (TypeError, ValueError):
            return "queue_depth_invalid"
    if not isinstance(saved.get("visited"), list):
        return "visited_not_list"
    if not isinstance(saved.get("listing_urls"), list):
        return "listing_urls_not_list"
    return None


def safe_parse_frontier(
    marketplace: DimMarketplace,
) -> tuple[deque[tuple[str, int]], set[str], list[str], bool, str | None]:
    """Deserialize frontier state; on corruption clear cursors and cold-start.

    Returns (queue, visited, listing_urls, was_corrupted, error_kind).
    Valid saved state matches parse_frontier output with was_corrupted=False.
    """
    saved = load_frontier_state(marketplace)
    if not saved:
        queue, visited, listing_urls = _cold_start_frontier(marketplace)
        return queue, visited, listing_urls, False, None

    error_kind = _frontier_schema_error_kind(saved)
    if error_kind is None:
        try:
            queue, visited, listing_urls = parse_frontier(saved)
            return queue, visited, listing_urls, False, None
        except Exception:
            error_kind = "parse_failed"

    clear_frontier(marketplace)
    set_category_resume_index(marketplace, 0)
    queue, visited, listing_urls = _cold_start_frontier(marketplace)
    return queue, visited, listing_urls, True, error_kind


def serialize_frontier(
    queue: deque[tuple[str, int]] | list[tuple[str, int]],
    visited: set[str],
    listing_urls: list[str],
) -> dict[str, Any]:
    """Serialize runtime BFS structures into recon_frontier_state JSONB shape."""
    return {
        "queue": [[u, d] for (u, d) in queue],
        "visited": list(visited),
        "listing_urls": list(listing_urls),
    }


def apply_frontier(
    marketplace: DimMarketplace,
    queue: deque[tuple[str, int]] | list[tuple[str, int]],
    visited: set[str],
    listing_urls: list[str],
) -> None:
    """Assign serialized frontier state on the marketplace ORM instance."""
    marketplace.recon_frontier_state = serialize_frontier(
        queue,
        visited,
        listing_urls,
    )


def clear_frontier(marketplace: DimMarketplace) -> None:
    """Clear recon_frontier_state on the marketplace ORM instance."""
    marketplace.recon_frontier_state = None


def get_sitemap_resume_offset(marketplace: DimMarketplace) -> int:
    """Read sitemap_resume_offset with legacy getattr/or coercion."""
    return int(getattr(marketplace, "sitemap_resume_offset", 0) or 0)


def set_sitemap_resume_offset(marketplace: DimMarketplace, offset: int) -> None:
    """Write sitemap_resume_offset on the marketplace ORM instance."""
    marketplace.sitemap_resume_offset = offset


def get_sitemap_bad_harvest_streak(marketplace: DimMarketplace) -> int:
    """Read sitemap_bad_harvest_streak with legacy getattr/or coercion."""
    return int(getattr(marketplace, "sitemap_bad_harvest_streak", 0) or 0)


def set_sitemap_bad_harvest_streak(marketplace: DimMarketplace, streak: int) -> None:
    """Write sitemap_bad_harvest_streak on the marketplace ORM instance."""
    marketplace.sitemap_bad_harvest_streak = streak


def get_phase1_exhausted_streak(marketplace: DimMarketplace) -> int:
    """Read phase1_exhausted_streak with legacy getattr/or coercion."""
    return int(getattr(marketplace, "phase1_exhausted_streak", 0) or 0)


def set_phase1_exhausted_streak(marketplace: DimMarketplace, streak: int) -> None:
    """Write phase1_exhausted_streak on the marketplace ORM instance."""
    marketplace.phase1_exhausted_streak = streak


def get_category_resume_index(marketplace: DimMarketplace) -> int:
    """Read category_resume_index with legacy getattr/or coercion."""
    return int(getattr(marketplace, "category_resume_index", 0) or 0)


def set_category_resume_index(marketplace: DimMarketplace, index: int) -> None:
    """Write category_resume_index on the marketplace ORM instance."""
    marketplace.category_resume_index = index


def get_discovered_category_urls(marketplace: DimMarketplace) -> list[str]:
    """Read discovered_category_urls from the marketplace ORM instance."""
    urls = marketplace.discovered_category_urls
    if not urls:
        return []
    return list(urls)


def set_discovered_category_urls(
    marketplace: DimMarketplace,
    urls: list[str],
) -> None:
    """Write discovered_category_urls on the marketplace ORM instance."""
    marketplace.discovered_category_urls = urls


def get_last_category_recon_at(
    marketplace: DimMarketplace,
) -> datetime | None:
    """Read last_category_recon_at from the marketplace ORM instance."""
    return marketplace.last_category_recon_at


def set_last_category_recon_at(
    marketplace: DimMarketplace,
    value: datetime,
) -> None:
    """Write last_category_recon_at on the marketplace ORM instance."""
    marketplace.last_category_recon_at = value


def get_last_sitemap_harvest_at(
    marketplace: DimMarketplace,
) -> datetime | None:
    """Read last_sitemap_harvest_at from the marketplace ORM instance."""
    return marketplace.last_sitemap_harvest_at


def set_last_sitemap_harvest_at(
    marketplace: DimMarketplace,
    value: datetime,
) -> None:
    """Write last_sitemap_harvest_at on the marketplace ORM instance."""
    marketplace.last_sitemap_harvest_at = value


def get_sitemap_url(marketplace: DimMarketplace) -> str | None:
    """Read sitemap_url from the marketplace ORM instance."""
    return marketplace.sitemap_url


def set_sitemap_url(marketplace: DimMarketplace, value: str) -> None:
    """Write sitemap_url on the marketplace ORM instance."""
    marketplace.sitemap_url = value


def snapshot_meta_columns(marketplace: DimMarketplace) -> dict[str, Any]:
    """Collect gated META snapshot columns from the marketplace ORM instance."""
    return {key: getattr(marketplace, key) for key in DISCOVERY_MP_WRITE_KEYS}
