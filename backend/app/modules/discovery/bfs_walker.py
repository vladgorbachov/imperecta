"""Phase 1 category BFS: discover listing/category URLs for Phase 2 harvest."""

from __future__ import annotations

import logging
import time
from collections import deque
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dimensions import DimMarketplace
from app.modules.discovery import classifier_adapter, cursor_store, fetch_adapter
from app.modules.discovery.alerting import (
    emit_discovery_service_alert,
    emit_fetch_empty_soup_spike_if_needed,
)
from app.modules.scraper.extractors import extract_internal_links_all
from app.modules.scraper.scraper_pool import ScraperPool

import structlog

logger = logging.getLogger(__name__)
slog = structlog.get_logger(__name__)

CATEGORY_PUBLISH_BATCH = 60
RECON_BFS_MAX_DEPTH = 3
PHASE1_EXHAUSTED_STREAK_THRESHOLD = 3


def _publish_category_batch(
    marketplace: DimMarketplace,
    listing_urls: list[str],
    queue,
    visited: set[str],
) -> list[str]:
    """Publish the current batch to discovered_category_urls for Phase 2.

    Keeps the BFS frontier (queue/visited) for continuation when the queue
    is non-empty (resets listing_urls for the next batch); does a true clean
    completion when the queue is empty (frontier cleared). Replaces
    discovered_category_urls with this batch (not append) so
    category_resume_index=0 indexes the fresh work-list.
    """
    seen: set[str] = set()
    unique: list[str] = []
    for url in listing_urls:
        if url not in seen:
            seen.add(url)
            unique.append(url)
    cursor_store.set_discovered_category_urls(marketplace, unique)
    cursor_store.set_category_resume_index(marketplace, 0)
    cursor_store.set_last_category_recon_at(
        marketplace,
        datetime.now(tz=timezone.utc),
    )
    if unique:
        cursor_store.set_phase1_exhausted_streak(marketplace, 0)
    if queue:
        cursor_store.apply_frontier(marketplace, queue, visited, [])
    else:
        cursor_store.clear_frontier(marketplace)
    return unique


async def run_category_bfs(
    marketplace: DimMarketplace,
    pool: ScraperPool,
    db: AsyncSession,
    *,
    deadline_monotonic: float | None = None,
    on_activity: Callable[[str], Awaitable[None]] | None = None,
) -> tuple[list[str], bool]:
    """Phase 1: BFS traversal to discover category/listing URLs.

    Returns (published_batch, exhausted_budget). ``published_batch`` is the
    listing URLs written to ``discovered_category_urls`` on this exit (batch
    publish, deadline publish, or final publish). Production callers should
    read the durable category backlog from ``cursor_store``; the tuple's first
    element is for observability and tests. ``exhausted_budget=True`` means
    the phase-1 time budget ran out with nothing published this tick.
    CATEGORY_PUBLISH_BATCH-sized batches so Phase 2 can harvest before the
    full BFS completes. On batch publish (threshold or deadline-with-findings)
    returns (batch, False) so discover() runs Phase 2 the same tick.
    exhausted=True means nothing was found this tick (no Phase 2 work).
    On true BFS completion (empty queue) publishes the final batch and
    clears the frontier. The incoming deadline is already headroom-adjusted
    by discover() — do not shrink again.
    """
    requires_js, scrape_tier = fetch_adapter.fetch_params_from_marketplace(marketplace)
    total_fetches = 0
    empty_fetches = 0

    def _record_fetch_result(soup: object | None) -> None:
        nonlocal total_fetches, empty_fetches
        total_fetches += 1
        if soup is None:
            empty_fetches += 1

    async def _emit_fetch_spike_if_needed() -> None:
        await emit_fetch_empty_soup_spike_if_needed(
            marketplace_id=marketplace.id,
            phase="category_bfs",
            total_fetches=total_fetches,
            empty_fetches=empty_fetches,
            requires_js=requires_js,
            scrape_tier=scrape_tier,
        )

    saved = cursor_store.load_frontier_state(marketplace)
    if saved:
        (
            queue,
            visited,
            listing_urls,
            was_corrupted,
            error_kind,
        ) = cursor_store.safe_parse_frontier(marketplace)
        if was_corrupted:
            await emit_discovery_service_alert(
                "cursor_store",
                "warning",
                "frontier_deserialize_failed",
                (
                    f"Frontier deserialize failed marketplace_id={marketplace.id}"
                ),
                marketplace_id=marketplace.id,
                context={
                    "error_kind": error_kind or "unknown",
                    "queue_len": len(queue),
                    "visited_len": len(visited),
                },
            )
            slog.warning(
                "discovery_frontier_deserialize_failed",
                marketplace_id=str(marketplace.id),
                error_kind=error_kind,
                queue_len=len(queue),
                visited_len=len(visited),
            )
        logger.info(
            "category_recon_resume marketplace_id=%s queue=%d "
            "visited=%d listing=%d corrupted=%s",
            marketplace.id,
            len(queue),
            len(visited),
            len(listing_urls),
            was_corrupted,
        )
    else:
        logger.info(
            "category_recon_start marketplace_id=%s url=%s",
            marketplace.id,
            marketplace.base_url,
        )
        queue = deque([(marketplace.base_url, 0)])
        visited = {marketplace.base_url}
        listing_urls = []
    fallback_seeds = ["/catalog", "/categories", "/shop", "/store", "/all"]

    # Heartbeat cadence inside the BFS: emit every Nth iteration (NOT per
    # fetch) so the worker_log_tail stays summary-level and DB-touch churn
    # stays bounded under should_pulse_db's own 15s window.
    recon_emit_every = 25
    bfs_iterations = 0
    while queue:
        if (
            deadline_monotonic is not None
            and time.monotonic() >= deadline_monotonic
        ):
            if listing_urls:
                unique = _publish_category_batch(
                    marketplace, listing_urls, queue, visited,
                )
                await db.flush()
                logger.info(
                    "category_recon_deadline_published marketplace_id=%s "
                    "published=%d queue=%d visited=%d",
                    marketplace.id,
                    len(unique),
                    len(queue),
                    len(visited),
                )
                await _emit_fetch_spike_if_needed()
                return unique, False
            cursor_store.apply_frontier(marketplace, queue, visited, [])
            await db.flush()
            streak = cursor_store.get_phase1_exhausted_streak(marketplace) + 1
            cursor_store.set_phase1_exhausted_streak(marketplace, streak)
            if len(queue) > 0 and len(listing_urls) == 0:
                await emit_discovery_service_alert(
                    "bfs_walker",
                    "warning",
                    "phase1_budget_exhausted_no_publish",
                    (
                        f"Phase 1 budget exhausted no publish "
                        f"marketplace_id={marketplace.id}"
                    ),
                    marketplace_id=marketplace.id,
                    context={
                        "queue_len": len(queue),
                        "visited_len": len(visited),
                        "listing_len": 0,
                        "depth_max": RECON_BFS_MAX_DEPTH,
                    },
                )
                slog.warning(
                    "discovery_phase1_budget_exhausted_no_publish",
                    marketplace_id=str(marketplace.id),
                    queue_len=len(queue),
                    visited_len=len(visited),
                    listing_len=0,
                    depth_max=RECON_BFS_MAX_DEPTH,
                )
            if streak >= PHASE1_EXHAUSTED_STREAK_THRESHOLD:
                await emit_discovery_service_alert(
                    "bfs_walker",
                    "info",
                    "phase1_repeated_exhausted",
                    (
                        f"Phase 1 repeated exhausted marketplace_id={marketplace.id} "
                        f"streak={streak}"
                    ),
                    marketplace_id=marketplace.id,
                    context={
                        "streak": streak,
                        "queue_len": len(queue),
                        "visited_len": len(visited),
                    },
                )
                slog.info(
                    "discovery_phase1_repeated_exhausted",
                    marketplace_id=str(marketplace.id),
                    streak=streak,
                    queue_len=len(queue),
                    visited_len=len(visited),
                )
            logger.info(
                "category_recon_budget_exhausted marketplace_id=%s "
                "queue=%d visited=%d listing=%d",
                marketplace.id,
                len(queue),
                len(visited),
                len(listing_urls),
            )
            await _emit_fetch_spike_if_needed()
            return listing_urls, True
        current_url, depth = queue.popleft()
        if depth > RECON_BFS_MAX_DEPTH:
            continue
        bfs_iterations += 1
        if bfs_iterations % recon_emit_every == 0 and on_activity is not None:
            await on_activity(
                f"discovery recon visited={len(visited)} "
                f"listing={len(listing_urls)}"
            )
        _html, soup = await fetch_adapter.fetch_page(
            pool,
            current_url,
            requires_js=requires_js,
            scrape_tier=scrape_tier,
        )
        _record_fetch_result(soup)
        if soup is None:
            continue
        role = classifier_adapter.classify_page_role(soup, current_url)
        logger.debug(
            "recon_page marketplace_id=%s url=%s depth=%d role=%s",
            marketplace.id,
            current_url,
            depth,
            role,
        )
        if role == "listing":
            if current_url != marketplace.base_url:
                listing_urls.append(current_url)
            if depth < RECON_BFS_MAX_DEPTH:
                for link in extract_internal_links_all(soup, marketplace.base_url):
                    if link not in visited:
                        visited.add(link)
                        queue.append((link, depth + 1))
            if len(listing_urls) >= CATEGORY_PUBLISH_BATCH:
                unique = _publish_category_batch(
                    marketplace, listing_urls, queue, visited,
                )
                await db.flush()
                logger.info(
                    "category_recon_batch_published marketplace_id=%s "
                    "published=%d queue_remaining=%d visited=%d",
                    marketplace.id,
                    len(unique),
                    len(queue),
                    len(visited),
                )
                await _emit_fetch_spike_if_needed()
                return unique, False
        elif role in ("hub", "unknown"):
            for link in extract_internal_links_all(soup, marketplace.base_url):
                if link not in visited:
                    visited.add(link)
                    queue.append((link, depth + 1))

    if not listing_urls:
        for fallback in fallback_seeds:
            fallback_url = f"{marketplace.base_url.rstrip('/')}{fallback}"
            if fallback_url in visited:
                continue
            _html, soup = await fetch_adapter.fetch_page(
                pool,
                fallback_url,
                requires_js=requires_js,
                scrape_tier=scrape_tier,
            )
            _record_fetch_result(soup)
            if soup is None:
                continue
            role = classifier_adapter.classify_page_role(soup, fallback_url)
            if role in ("listing", "hub"):
                listing_urls.append(fallback_url)

    unique = _publish_category_batch(
        marketplace, listing_urls, queue, visited,
    )
    await db.flush()
    logger.info(
        "category_recon_done marketplace_id=%s listing_urls_found=%d",
        marketplace.id,
        len(unique),
    )
    await _emit_fetch_spike_if_needed()
    return unique, False
