"""Phase 0 sitemap harvest: fetch candidates, classify-gate, cooldown cursor writes."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dimensions import DimMarketplace
from app.modules.discovery import cursor_store, fetch_adapter
from app.modules.discovery.alerting import emit_discovery_service_alert
from app.modules.discovery.category_processor import FilterUrlsByRoleFn
from app.modules.discovery.constants import SITEMAP_FULL_CLASSIFY_LIMIT
from app.modules.scraper.scraper_pool import ScraperPool

logger = logging.getLogger(__name__)
slog = structlog.get_logger(__name__)

# Values must match discovery/constants.py (orchestrator imports the same).
SITEMAP_MIN_USEFUL_URLS = 10
SITEMAP_STALE_DAYS = 3
SITEMAP_BAD_HARVEST_RETRY_HOURS = 1
SITEMAP_USEFUL_FALSE_STREAK_THRESHOLD = 3


async def harvest_sitemap(
    marketplace: DimMarketplace,
    pool: ScraperPool,
    db: AsyncSession,
    *,
    filter_urls_by_role: FilterUrlsByRoleFn,
    on_activity: Callable[[str], Awaitable[None]] | None = None,
) -> list[str]:
    """Phase 0: collect product URLs from XML sitemaps with content-aware filtering.

    Pipeline:
    1. Fetch raw URLs from sitemap (delegated to ScraperPool.fetch_sitemap_candidates).
    2. Classify each URL (or a sample) via classify_page_role to keep only PDPs.
    3. Decide cooldown adaptively:
       - useful harvest → mark fresh, full SITEMAP_STALE_DAYS cooldown.
       - bad harvest    → shift last_sitemap_harvest_at so the marketplace
                          becomes stale again after SITEMAP_BAD_HARVEST_RETRY_HOURS.

    Returns only the URLs classified as 'product'.
    """
    # Reserved for future worker_log_tail activity hooks (orchestrator passes callback).
    _ = on_activity
    logger.info(
        "sitemap_harvest_start marketplace_id=%s url=%s",
        marketplace.id,
        marketplace.base_url,
    )
    raw_urls = await pool.fetch_sitemap_candidates(
        marketplace.base_url,
        marketplace_locale=marketplace.locale,
    )

    last_harvest_known = (
        cursor_store.get_last_sitemap_harvest_at(marketplace) is not None
        or cursor_store.get_sitemap_url(marketplace) is not None
    )
    if len(raw_urls) == 0 and last_harvest_known:
        await emit_discovery_service_alert(
            "sitemap_harvester",
            "warning",
            "sitemap_raw_empty",
            f"Sitemap raw empty marketplace_id={marketplace.id}",
            marketplace_id=marketplace.id,
            context={
                "raw": 0,
                "last_harvest_known": True,
            },
        )
        slog.warning(
            "discovery_sitemap_raw_empty",
            marketplace_id=str(marketplace.id),
            raw=0,
            last_harvest_known=True,
        )

    requires_js, scrape_tier = fetch_adapter.fetch_params_from_marketplace(marketplace)
    filtered_urls, classify_stats = await filter_urls_by_role(
        raw_urls,
        requires_js=requires_js,
        scrape_tier=scrape_tier,
        marketplace_locale=marketplace.locale,
    )
    rejected_count = len(raw_urls) - len(filtered_urls)
    classify_mode = classify_stats.get("mode")
    if (
        classify_mode == "reject_sample"
        and len(raw_urls) >= SITEMAP_FULL_CLASSIFY_LIMIT
    ):
        await emit_discovery_service_alert(
            "sitemap_harvester",
            "warning",
            "sitemap_reject_sample",
            (
                f"Sitemap sample gate rejected marketplace_id={marketplace.id} "
                f"raw={len(raw_urls)}"
            ),
            marketplace_id=marketplace.id,
            context={
                "raw": len(raw_urls),
                "filtered": len(filtered_urls),
                "mode": classify_mode,
                "sample_ratio": classify_stats.get("sample_product_ratio"),
            },
        )
        slog.warning(
            "discovery_sitemap_reject_sample",
            marketplace_id=str(marketplace.id),
            raw=len(raw_urls),
            filtered=len(filtered_urls),
            mode=classify_mode,
            sample_ratio=classify_stats.get("sample_product_ratio"),
        )

    useful = len(filtered_urls) >= SITEMAP_MIN_USEFUL_URLS

    now = datetime.now(tz=timezone.utc)
    if useful:
        cursor_store.set_sitemap_bad_harvest_streak(marketplace, 0)
        cursor_store.set_last_sitemap_harvest_at(marketplace, now)
        # Approximation — actual sitemap location is resolved by
        # fetch_sitemap_candidates via robots.txt + common paths.
        cursor_store.set_sitemap_url(
            marketplace,
            f"{marketplace.base_url.rstrip('/')}/sitemap.xml",
        )
    else:
        streak = cursor_store.get_sitemap_bad_harvest_streak(marketplace) + 1
        cursor_store.set_sitemap_bad_harvest_streak(marketplace, streak)
        if streak >= SITEMAP_USEFUL_FALSE_STREAK_THRESHOLD:
            await emit_discovery_service_alert(
                "sitemap_harvester",
                "info",
                "sitemap_useful_false",
                (
                    f"Sitemap useful false streak marketplace_id={marketplace.id} "
                    f"streak={streak}"
                ),
                marketplace_id=marketplace.id,
                context={
                    "streak": streak,
                    "raw": len(raw_urls),
                    "filtered": len(filtered_urls),
                },
            )
            slog.info(
                "discovery_sitemap_useful_false",
                marketplace_id=str(marketplace.id),
                streak=streak,
                raw=len(raw_urls),
                filtered=len(filtered_urls),
            )
        # Treat as bad harvest: pretend it happened just before the stale
        # threshold so the next discovery cycle retries after
        # SITEMAP_BAD_HARVEST_RETRY_HOURS instead of SITEMAP_STALE_DAYS.
        # sitemap_url is NOT updated on bad harvest — keep prior value.
        retry_offset = timedelta(
            days=SITEMAP_STALE_DAYS,
            hours=-SITEMAP_BAD_HARVEST_RETRY_HOURS,
        )
        cursor_store.set_last_sitemap_harvest_at(marketplace, now - retry_offset)

    await db.flush()
    logger.info(
        "sitemap_harvest_done marketplace_id=%s raw=%d filtered=%d rejected=%d "
        "useful=%s classify_mode=%s sampled=%s sample_product_ratio=%s",
        marketplace.id,
        len(raw_urls),
        len(filtered_urls),
        rejected_count,
        useful,
        classify_stats.get("mode"),
        classify_stats.get("sampled"),
        classify_stats.get("sample_product_ratio"),
    )
    return filtered_urls
