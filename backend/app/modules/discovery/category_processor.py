"""Phase 2 category harvest: paginate categories, gate product URLs, save to pool."""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable
from typing import Protocol
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dimensions import DimMarketplace
from app.modules.discovery import fetch_adapter
from app.modules.discovery.alerting import (
    emit_discovery_service_alert,
    emit_fetch_empty_soup_spike_if_needed,
)
from app.modules.scraper.extractors import (
    detect_next_page,
    extract_links_from_repeated_structure,
    extract_product_links,
)
from app.modules.scraper.scraper_pool import ScraperPool

logger = logging.getLogger(__name__)
slog = structlog.get_logger(__name__)

MAX_CATEGORY_URLS_PER_RUN = 60
MAX_PAGES_PER_CATEGORY = 50
CATEGORY_CONVERGENCE_STREAK = 3


class FilterUrlsByRoleFn(Protocol):
    """Structural product gate used by Phase 0 sitemap and Phase 2 harvest."""

    async def __call__(
        self,
        urls: list[str],
        *,
        requires_js: bool,
        scrape_tier: int,
        marketplace_locale: str | None = None,
        marketplace_id: UUID | None = None,
    ) -> tuple[list[str], dict[str, int | float | str | None]]: ...


class SaveProductUrlsFn(Protocol):
    """Shared pool-save utility (sitemap path + Phase 2)."""

    async def __call__(
        self,
        marketplace_id: UUID,
        urls: list[str],
        *,
        start_offset: int = 0,
        deadline_monotonic: float | None = None,
    ) -> tuple[int, int, bool]: ...


async def _gate_urls_for_pool(
    urls: list[str],
    marketplace: DimMarketplace,
    *,
    filter_urls_by_role: FilterUrlsByRoleFn,
) -> list[str]:
    """Structural product-ness gate for category-harvest candidate URLs."""
    if not urls:
        return []
    requires_js, scrape_tier = fetch_adapter.fetch_params_from_marketplace(marketplace)
    accepted, _stats = await filter_urls_by_role(
        urls,
        requires_js=requires_js,
        scrape_tier=scrape_tier,
        marketplace_locale=marketplace.locale,
        marketplace_id=marketplace.id,
    )
    return accepted


async def run_product_harvest(
    marketplace: DimMarketplace,
    pool: ScraperPool,
    db: AsyncSession,
    category_urls: list[str],
    *,
    start_index: int = 0,
    deadline_monotonic: float | None = None,
    on_activity: Callable[[str], Awaitable[None]] | None = None,
    filter_urls_by_role: FilterUrlsByRoleFn,
    save_product_urls: SaveProductUrlsFn,
) -> tuple[int, int, bool]:
    """Phase 2: crawl each category URL, extract product links, save to pool.

    Returns (total_saved, next_index, more_remaining) per the cursor state machine.
    The incoming deadline is already headroom-adjusted by discover() — pass through
    unchanged.
    """
    _ = db

    requires_js, scrape_tier = fetch_adapter.fetch_params_from_marketplace(marketplace)
    total_fetches = 0
    empty_fetches = 0

    def _record_fetch_result(soup: object | None) -> None:
        nonlocal total_fetches, empty_fetches
        total_fetches += 1
        if soup is None:
            empty_fetches += 1

    total_saved = 0
    empty_streak = 0
    categories_processed = 0
    candidate_urls_extracted = 0
    gated_urls_accepted = 0
    total_categories = len(category_urls)
    harvest_targets = category_urls[
        start_index : start_index + MAX_CATEGORY_URLS_PER_RUN
    ]
    more_remaining = False
    next_index = 0
    converged = False

    for relative_idx, category_url in enumerate(harvest_targets):
        absolute_idx = start_index + relative_idx
        if (
            deadline_monotonic is not None
            and time.monotonic() >= deadline_monotonic
        ):
            logger.info(
                "discovery_phase2_budget_exhausted marketplace_id=%s "
                "categories_processed=%d categories_total=%d "
                "total_saved=%d next_index=%d",
                marketplace.id,
                absolute_idx,
                total_categories,
                total_saved,
                absolute_idx,
            )
            more_remaining = True
            next_index = absolute_idx
            break

        categories_processed += 1
        saved_for_this_category = 0
        current_url: str | None = category_url
        page_num = 0
        while current_url and page_num < MAX_PAGES_PER_CATEGORY:
            if (
                deadline_monotonic is not None
                and time.monotonic() >= deadline_monotonic
            ):
                more_remaining = True
                next_index = absolute_idx
                break

            _html, soup = await fetch_adapter.fetch_page(
                pool,
                current_url,
                requires_js=requires_js,
                scrape_tier=scrape_tier,
            )
            _record_fetch_result(soup)
            if soup is None:
                break

            if on_activity is not None:
                await on_activity(
                    f"discovery GET {current_url[:140]} page={page_num + 1}",
                )

            product_urls = extract_links_from_repeated_structure(
                soup,
                marketplace.base_url,
                current_url,
            )
            if not product_urls:
                product_urls = extract_product_links(soup, marketplace.base_url)
            if product_urls:
                candidate_urls_extracted += len(product_urls)
                gated_urls = await _gate_urls_for_pool(
                    product_urls,
                    marketplace,
                    filter_urls_by_role=filter_urls_by_role,
                )
                gated_urls_accepted += len(gated_urls)
                saved_this_call = 0
                save_exhausted = False
                if gated_urls:
                    saved_this_call, _, save_exhausted = await save_product_urls(
                        marketplace.id,
                        gated_urls,
                        deadline_monotonic=deadline_monotonic,
                    )
                saved_for_this_category += saved_this_call
                total_saved += saved_this_call
                if save_exhausted:
                    more_remaining = True
                    next_index = absolute_idx
                    break

            next_page = detect_next_page(soup, current_url)
            current_url = next_page
            page_num += 1

        if more_remaining:
            break

        if saved_for_this_category == 0:
            empty_streak += 1
        else:
            empty_streak = 0

        if empty_streak >= CATEGORY_CONVERGENCE_STREAK:
            logger.info(
                "discovery_phase2_converged marketplace_id=%s "
                "categories_processed=%d categories_total=%d total_saved=%d "
                "empty_streak=%d",
                marketplace.id,
                relative_idx + 1,
                len(harvest_targets),
                total_saved,
                empty_streak,
            )
            converged = True
            break

    if more_remaining:
        pass
    elif converged:
        next_index = 0
        more_remaining = False
    else:
        end_index = start_index + len(harvest_targets)
        if end_index < total_categories:
            next_index = end_index
            more_remaining = True
        else:
            next_index = 0
            more_remaining = False

    if (
        total_saved == 0
        and categories_processed >= CATEGORY_CONVERGENCE_STREAK
        and candidate_urls_extracted > 0
    ):
        await emit_discovery_service_alert(
            "category_processor",
            "warning",
            "phase2_zero_yield",
            (
                f"Phase 2 zero yield marketplace_id={marketplace.id} "
                f"candidate_urls_extracted={candidate_urls_extracted}"
            ),
            marketplace_id=marketplace.id,
            context={
                "categories_processed": categories_processed,
                "total_saved": total_saved,
                "candidate_urls_extracted": candidate_urls_extracted,
                "gated_urls_accepted": gated_urls_accepted,
            },
        )
        slog.warning(
            "discovery_phase2_zero_yield",
            marketplace_id=str(marketplace.id),
            categories_processed=categories_processed,
            total_saved=total_saved,
            candidate_urls_extracted=candidate_urls_extracted,
            gated_urls_accepted=gated_urls_accepted,
        )
    elif converged and total_saved == 0:
        await emit_discovery_service_alert(
            "category_processor",
            "info",
            "phase2_converged_empty",
            (
                f"Phase 2 converged empty marketplace_id={marketplace.id} "
                f"categories_processed={categories_processed}"
            ),
            marketplace_id=marketplace.id,
            context={
                "categories_processed": categories_processed,
                "empty_streak": empty_streak,
                "total_saved": total_saved,
            },
        )
        slog.info(
            "discovery_phase2_converged_empty",
            marketplace_id=str(marketplace.id),
            categories_processed=categories_processed,
            empty_streak=empty_streak,
            total_saved=total_saved,
        )

    await emit_fetch_empty_soup_spike_if_needed(
        marketplace_id=marketplace.id,
        phase="category_harvest",
        total_fetches=total_fetches,
        empty_fetches=empty_fetches,
        requires_js=requires_js,
        scrape_tier=scrape_tier,
    )

    return total_saved, next_index, more_remaining
