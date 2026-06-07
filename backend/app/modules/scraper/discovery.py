"""Discovery crawler: DimMarketplace → listing pages → DimProduct + FactListing."""

import asyncio
import logging
import random
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models.app_tables import ScrapeJob
from app.models.dimensions import DimMarketplace, DimProduct
from app.models.facts import FactListing
from app.modules.scraper.extractors import classify_page_role_for_discovery
from app.modules.scraper.scraper_pool import ScraperPool

logger = logging.getLogger(__name__)

# Days before category recon is re-run for a marketplace.
CATEGORY_RECON_STALE_DAYS = 7
# Days before sitemap harvest is re-run.
SITEMAP_STALE_DAYS = 3
# Max category URLs to harvest products from per discovery run.
MAX_CATEGORY_URLS_PER_RUN = 60
# Max pages to paginate within a single category URL.
MAX_PAGES_PER_CATEGORY = 50
# Convergence detection for _phase2_product_harvest:
# If this many consecutive category iterations yield zero NEW persisted PDP,
# discovery for this marketplace is considered converged and exits early.
# This is a universal mechanism, not tuned to any specific marketplace —
# small/exhausted shops converge quickly, large shops continue iterating.
CATEGORY_CONVERGENCE_STREAK = 3
# Persist batch size for _save_product_urls. Large sitemaps (e.g., 20k+ URLs)
# cannot be saved in a single transaction within DISCOVERY_PER_MARKETPLACE_BUDGET_SECONDS —
# the monolithic flush takes >14 minutes and gets cancelled by the circuit breaker,
# losing all work. Batched commits ensure progress survives cancel: each committed
# batch is durable, and the next run sees its URLs via existing_hashes lookup.
#
# 500 is a balance between round-trip overhead (smaller batches = more flushes)
# and lost-work-on-cancel (larger batches = bigger loss when cancel hits mid-batch).
SAVE_PRODUCT_URLS_BATCH_SIZE = 500
# Fraction of the per-marketplace discovery budget that
# _save_product_urls is allowed to consume before voluntarily
# exiting with a resumable offset. The remaining 15% is
# headroom for finalization (final commit of marketplace row,
# status updates, return path) so the caller never has to
# hard-cancel us mid-commit.
SAVE_BUDGET_HEADROOM_FRACTION = 0.85
# Max BFS depth when exploring hub pages for category links.
RECON_BFS_MAX_DEPTH = 3
# Min URLs found via sitemap to consider sitemap harvest successful.
SITEMAP_MIN_USEFUL_URLS = 10
# Sampling strategy for content-aware sitemap classification.
# If sitemap returns <= SITEMAP_FULL_CLASSIFY_LIMIT URLs, classify all of them.
# Otherwise classify only a random sample to decide whether to trust the sitemap.
SITEMAP_FULL_CLASSIFY_LIMIT = 100
# Size of random sample taken from large sitemaps for trust assessment.
SITEMAP_SAMPLE_SIZE = 50
# If at least this fraction of the sample classifies as 'product',
# accept the entire sitemap without further per-URL classification.
SITEMAP_TRUST_THRESHOLD = 0.80
# If less than this fraction of the sample classifies as 'product',
# reject the entire sitemap and fall back to category recon.
SITEMAP_REJECT_THRESHOLD = 0.20
# Max concurrent classification fetches (HTTP throttle).
SITEMAP_CLASSIFY_CONCURRENCY = 8
# After a sitemap harvest that produced too few useful product URLs,
# treat the result as unsuccessful and retry shortly instead of caching
# for SITEMAP_STALE_DAYS.
SITEMAP_BAD_HARVEST_RETRY_HOURS = 1

# ---------------------------------------------------------------------------
# Universal timeout policy: three-level defence against slow/broken marketplaces.
# ---------------------------------------------------------------------------
# These budgets bound how long discovery can spend per marketplace, ensuring
# one slow or unreachable site cannot stall the entire pipeline. Values are
# intentionally permissive to keep correctness as the priority — fast retries
# would risk losing slow-but-valid marketplaces. Tuning happens via these
# constants only; no per-marketplace overrides.

# Per sitemap-phase budget. If _phase0_sitemap_harvest does not produce URLs
# within this window, the sitemap path is abandoned and discovery falls back
# to category-recon path for this marketplace.
SITEMAP_PHASE_BUDGET_SECONDS = 300  # 5 minutes

# Per-marketplace total discovery budget (sitemap + category recon together).
# If the full discover() call exceeds this, the marketplace is marked as
# timeout_skipped with 24-hour cooldown and the pipeline continues with the
# next marketplace.
DISCOVERY_PER_MARKETPLACE_BUDGET_SECONDS = 900  # 15 minutes

# Cooldown applied to sitemap_harvest when sitemap times out (asyncio.TimeoutError).
# Longer than SITEMAP_BAD_HARVEST_RETRY_HOURS because a timeout signals a
# persistent issue (very slow server, anti-bot, network partition) — retrying
# in an hour would just burn another budget cycle.
SITEMAP_TIMEOUT_COOLDOWN_HOURS = 24


def _title_from_url(url: str) -> str:
    """Derive placeholder product title from URL path."""
    path = urlparse(url).path.strip("/").split("/")[-1]
    if path:
        return path.replace("-", " ").replace("_", " ")[:500]
    return (url or "product")[:500]


def _normalize_name(name: str) -> str:
    return " ".join((name or "").lower().split())[:500]


@dataclass
class DiscoveryResult:
    """Result of discovering product URLs on a marketplace.

    Field groups:
    - Mandatory/system: marketplace_id, status, started_at, completed_at
    - Counts: pages_scanned, candidate_urls_found, accepted_urls,
      duplicate_urls, rejected_urls, persisted_listings
    - Technical: job_id, errors, discovery_method
    """

    marketplace_id: UUID
    status: str  # completed, partial, partial_budget,
    # error, no_categories
    started_at: datetime
    completed_at: datetime | None = None

    # Counts
    pages_scanned: int = 0
    candidate_urls_found: int = 0
    accepted_urls: int = 0
    duplicate_urls: int = 0
    rejected_urls: int = 0
    persisted_listings: int = 0

    # Technical
    job_id: UUID | None = None
    errors: list[str] = field(default_factory=list)
    discovery_method: str = "category_crawl"


class DiscoveryCrawler:
    """Crawl marketplace listing pages and persist discovered product URLs."""

    def __init__(
        self,
        db: AsyncSession,
        scraper_pool: ScraperPool,
        *,
        on_activity: Callable[[str], Awaitable[None]] | None = None,
    ):
        self.db = db
        self.pool = scraper_pool
        self._on_activity = on_activity

    async def _emit_activity(self, line: str) -> None:
        if self._on_activity is None:
            return
        await self._on_activity(line)

    @staticmethod
    def _seed_candidates(seed_url: str) -> list[str]:
        """Generate alternative category/listing entry URLs for marketplaces."""
        parsed = urlparse(seed_url)
        if not parsed.scheme or not parsed.netloc:
            return [seed_url]
        origin = f"{parsed.scheme}://{parsed.netloc}"
        raw_path = (parsed.path or "").strip("/")
        candidates: list[str] = [seed_url]
        if raw_path:
            candidates.append(f"{origin}/{raw_path}")
        fallbacks = (
            "catalog",
            "products",
            "shop",
            "categories",
            "collections",
            "ru/catalog",
            "ua/catalog",
            "bg/catalog",
            "en/catalog",
        )
        for fallback in fallbacks:
            candidates.append(f"{origin}/{fallback}")
        # Preserve order, remove duplicates.
        seen: set[str] = set()
        out: list[str] = []
        for url in candidates:
            if url in seen:
                continue
            seen.add(url)
            out.append(url)
        return out

    @staticmethod
    def _headroom_deadline(
        deadline_monotonic: float | None,
    ) -> float | None:
        """Shrink a hard deadline by SAVE_BUDGET_HEADROOM_FRACTION.

        Reserves the remaining fraction of the budget for
        finalization (final commits, marketplace row updates, the
        return path) so a phase voluntarily stops before the
        caller's hard deadline, never mid-commit. Returns None when
        no deadline is set (unbounded run).
        """
        if deadline_monotonic is None:
            return None
        now_m = time.monotonic()
        remaining_budget = max(0.0, deadline_monotonic - now_m)
        return now_m + (
            remaining_budget * SAVE_BUDGET_HEADROOM_FRACTION
        )

    async def _save_product_urls(
        self,
        marketplace_id: UUID,
        urls: list[str],
        *,
        start_offset: int = 0,
        deadline_monotonic: float | None = None,
    ) -> tuple[int, int, bool]:
        """Save discovered URLs. Returns (new_count, next_offset, exhausted_budget).

        next_offset is the absolute index (into the original `urls` list) at
        which a subsequent call should resume. When all entries are processed
        without hitting the deadline, next_offset == len(urls) and
        exhausted_budget == False.

        When deadline_monotonic is set and time.monotonic() reaches it BETWEEN
        batch commits, the loop commits its current batch, stops, and returns
        (new_count_so_far, absolute_index_after_last_commit, True). The
        deadline is never checked mid-commit — only after a successful commit
        returns control.
        """
        if not urls:
            return 0, start_offset, False

        work_urls = urls[start_offset:] if start_offset > 0 else urls
        normalized_urls = [u for u in work_urls if u]
        hash_by_url = {url: FactListing.compute_url_hash(url) for url in normalized_urls}
        existing_hashes_result = await self.db.execute(
            select(FactListing.url_hash).where(FactListing.url_hash.in_(list(hash_by_url.values()))),
        )
        existing_hashes = {row[0] for row in existing_hashes_result.all() if row[0]}

        new_count = 0
        pending_in_batch = 0
        for relative_index, url in enumerate(normalized_urls):
            url_hash = hash_by_url[url]
            if url_hash in existing_hashes:
                continue

            title = _title_from_url(url) or "product"
            product_id = uuid4()
            product = DimProduct(
                id=product_id,
                name=title,
                name_normalized=_normalize_name(title) or "product",
                is_active=True,
            )
            self.db.add(product)

            listing = FactListing(
                product_id=product_id,
                marketplace_id=marketplace_id,
                external_url=url,
                url_hash=url_hash,
                is_active=True,
            )
            self.db.add(listing)
            existing_hashes.add(url_hash)
            new_count += 1
            pending_in_batch += 1

            if pending_in_batch >= SAVE_PRODUCT_URLS_BATCH_SIZE:
                await self.db.commit()
                pending_in_batch = 0
                # absolute_index points to the URL we just FINISHED
                # processing in the original list. The next run
                # should resume from this index (inclusive of any
                # already-saved URL, which existing_hashes will skip).
                absolute_index = start_offset + relative_index + 1
                logger.info(
                    "save_product_urls_progress marketplace_id=%s "
                    "absolute_offset=%d new_in_run=%d batch_size=%d",
                    marketplace_id,
                    absolute_index,
                    new_count,
                    SAVE_PRODUCT_URLS_BATCH_SIZE,
                )
                if (
                    deadline_monotonic is not None
                    and time.monotonic() >= deadline_monotonic
                ):
                    return new_count, absolute_index, True

        if pending_in_batch > 0:
            await self.db.commit()
        return new_count, start_offset + len(normalized_urls), False

    def _should_run_sitemap_harvest(self, marketplace: DimMarketplace) -> bool:
        """Return True if sitemap harvest should run."""
        if int(getattr(marketplace, "sitemap_resume_offset", 0) or 0) > 0:
            return True
        if marketplace.last_sitemap_harvest_at is None:
            return True
        age = (datetime.now(tz=timezone.utc) - marketplace.last_sitemap_harvest_at).days
        return age >= SITEMAP_STALE_DAYS

    async def _classify_url(self, url: str) -> str:
        """Fetch a URL statically and return its page-role classification.

        Returns one of:
        - 'product' — page is a single product detail page (PDP).
        - 'listing' — page lists multiple products (category, search results, etc.).
        - 'hub'     — navigational page with no products (homepage, about, etc.).
        - 'unknown' — fetch failed or signals were inconclusive.

        Pure content-based classification: no URL pattern matching, no language-specific
        keywords. Works for any marketplace in any language.
        """
        try:
            _html, soup = await self.pool.scrape_page_for_analysis(
                url,
                static_fetch=True,
            )
        except Exception:
            return "unknown"
        if soup is None:
            return "unknown"
        try:
            return classify_page_role_for_discovery(soup, url)
        except Exception:
            return "unknown"

    async def _filter_urls_by_role(
        self,
        urls: list[str],
    ) -> tuple[list[str], dict[str, int | float | str | None]]:
        """Classify a list of URLs concurrently and return only product PDPs.

        Strategy:
        - For small lists (<= SITEMAP_FULL_CLASSIFY_LIMIT) classify everything.
        - For larger lists, classify a random sample first:
          - If >= SITEMAP_TRUST_THRESHOLD of the sample are products → trust
            the entire input as product URLs (avoids classifying tens of thousands).
          - If < SITEMAP_REJECT_THRESHOLD are products → reject the entire input
            (the source is not product-oriented), but keep PDPs found in sample.
          - Otherwise → fall back to full classification.

        Concurrency is bounded by SITEMAP_CLASSIFY_CONCURRENCY via asyncio.Semaphore
        to avoid overloading the target server.

        Returns (accepted_urls, stats_dict) where stats_dict contains:
            total, sampled, sample_product_ratio, classified, accepted, mode.
        In 'full' and 'trust_sample' modes, 'sampled' is None to distinguish
        from 'sampled=0' which would mean an empty sample.
        """
        stats: dict[str, int | float | str | None] = {
            "total": len(urls),
            "sampled": None,
            "sample_product_ratio": None,
            "classified": 0,
            "accepted": 0,
            "mode": "none",
        }
        if not urls:
            stats["mode"] = "empty"
            return [], stats

        semaphore = asyncio.Semaphore(SITEMAP_CLASSIFY_CONCURRENCY)

        async def classify_one(target_url: str) -> tuple[str, str]:
            async with semaphore:
                role = await self._classify_url(target_url)
                return target_url, role

        # Small input: classify everything.
        if len(urls) <= SITEMAP_FULL_CLASSIFY_LIMIT:
            stats["mode"] = "full"
            results = await asyncio.gather(*(classify_one(u) for u in urls))
            stats["classified"] = len(results)
            accepted = [u for u, role in results if role == "product"]
            stats["accepted"] = len(accepted)
            return accepted, stats

        # Large input: sample first.
        sample_size = min(SITEMAP_SAMPLE_SIZE, len(urls))
        sample = random.sample(urls, sample_size)
        sample_results = await asyncio.gather(*(classify_one(u) for u in sample))
        stats["sampled"] = len(sample_results)
        product_in_sample = sum(1 for _u, role in sample_results if role == "product")
        ratio = product_in_sample / len(sample_results) if sample_results else 0.0
        stats["sample_product_ratio"] = round(ratio, 3)

        if ratio >= SITEMAP_TRUST_THRESHOLD:
            # Sample statistically vouches for the source; accept all input URLs.
            stats["mode"] = "trust_sample"
            stats["accepted"] = len(urls)
            return list(urls), stats

        if ratio < SITEMAP_REJECT_THRESHOLD:
            # Source is not product-oriented; reject everything except the actual
            # product URLs we already discovered in the sample (those are real PDPs).
            stats["mode"] = "reject_sample"
            sample_products = [u for u, role in sample_results if role == "product"]
            stats["accepted"] = len(sample_products)
            return sample_products, stats

        # Borderline ratio (20-80%): fall through to full classification.
        # Reuse already-classified sample results, classify only the rest.
        stats["mode"] = "full_fallback"
        sample_urls_set = {u for u, _r in sample_results}
        remaining = [u for u in urls if u not in sample_urls_set]
        remaining_results = await asyncio.gather(*(classify_one(u) for u in remaining))
        all_results = list(sample_results) + list(remaining_results)
        stats["classified"] = len(all_results)
        accepted = [u for u, role in all_results if role == "product"]
        stats["accepted"] = len(accepted)
        return accepted, stats

    async def _phase0_sitemap_harvest(self, marketplace: DimMarketplace) -> list[str]:
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
        logger.info(
            "sitemap_harvest_start marketplace_id=%s url=%s",
            marketplace.id,
            marketplace.base_url,
        )
        raw_urls = await self.pool.fetch_sitemap_candidates(marketplace.base_url)

        filtered_urls, classify_stats = await self._filter_urls_by_role(raw_urls)
        rejected_count = len(raw_urls) - len(filtered_urls)
        useful = len(filtered_urls) >= SITEMAP_MIN_USEFUL_URLS

        now = datetime.now(tz=timezone.utc)
        if useful:
            marketplace.last_sitemap_harvest_at = now
            # Approximation — actual sitemap location is resolved by
            # fetch_sitemap_candidates via robots.txt + common paths.
            marketplace.sitemap_url = f"{marketplace.base_url.rstrip('/')}/sitemap.xml"
        else:
            # Treat as bad harvest: pretend it happened just before the stale
            # threshold so the next discovery cycle retries after
            # SITEMAP_BAD_HARVEST_RETRY_HOURS instead of SITEMAP_STALE_DAYS.
            # sitemap_url is NOT updated on bad harvest — keep prior value.
            retry_offset = timedelta(
                days=SITEMAP_STALE_DAYS,
                hours=-SITEMAP_BAD_HARVEST_RETRY_HOURS,
            )
            marketplace.last_sitemap_harvest_at = now - retry_offset

        await self.db.flush()
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

    def _should_run_category_recon(self, marketplace: DimMarketplace) -> bool:
        """Return True if category recon should run."""
        if int(getattr(marketplace, "category_resume_index", 0) or 0) > 0:
            return False
        if marketplace.recon_frontier_state:
            return True
        if not marketplace.discovered_category_urls:
            return True
        if marketplace.last_category_recon_at is None:
            return True
        age = (datetime.now(tz=timezone.utc) - marketplace.last_category_recon_at).days
        return age >= CATEGORY_RECON_STALE_DAYS

    async def _phase1_category_recon(
        self,
        marketplace: DimMarketplace,
        *,
        deadline_monotonic: float | None = None,
    ) -> tuple[list[str], bool]:
        """Phase 1: BFS traversal to discover category/listing URLs.

        Returns (listing_urls, exhausted_budget). On deadline expiry the
        BFS frontier (queue, visited, listing_urls) is persisted to
        marketplace.recon_frontier_state and the method returns
        (current_listing_urls, True); a later run resumes from the
        frontier. On natural completion the frontier is cleared (None)
        and discovered_category_urls is written. The incoming deadline
        is already headroom-adjusted by discover() — do not shrink again.
        """
        from collections import deque

        from app.modules.scraper.extractors import (
            classify_page_role_for_discovery,
            extract_internal_links_all,
        )

        saved = marketplace.recon_frontier_state
        if saved:
            queue: deque[tuple[str, int]] = deque(
                (str(item[0]), int(item[1]))
                for item in saved.get("queue", [])
            )
            visited: set[str] = set(saved.get("visited", []))
            listing_urls: list[str] = list(saved.get("listing_urls", []))
            logger.info(
                "category_recon_resume marketplace_id=%s queue=%d "
                "visited=%d listing=%d",
                marketplace.id,
                len(queue),
                len(visited),
                len(listing_urls),
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

        while queue:
            if (
                deadline_monotonic is not None
                and time.monotonic() >= deadline_monotonic
            ):
                marketplace.recon_frontier_state = {
                    "queue": [[u, d] for (u, d) in queue],
                    "visited": list(visited),
                    "listing_urls": listing_urls,
                }
                await self.db.flush()
                logger.info(
                    "category_recon_budget_exhausted marketplace_id=%s "
                    "queue=%d visited=%d listing=%d",
                    marketplace.id,
                    len(queue),
                    len(visited),
                    len(listing_urls),
                )
                return listing_urls, True
            current_url, depth = queue.popleft()
            if depth > RECON_BFS_MAX_DEPTH:
                continue
            _html, soup = await self.pool.scrape_page_for_analysis(
                current_url,
                static_fetch=True,
            )
            if soup is None:
                continue
            role = classify_page_role_for_discovery(soup, marketplace.base_url)
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
                _html, soup = await self.pool.scrape_page_for_analysis(
                    fallback_url,
                    static_fetch=True,
                )
                if soup is None:
                    continue
                role = classify_page_role_for_discovery(soup, marketplace.base_url)
                if role in ("listing", "hub"):
                    listing_urls.append(fallback_url)

        seen: set[str] = set()
        unique: list[str] = []
        for url in listing_urls:
            if url not in seen:
                seen.add(url)
                unique.append(url)

        marketplace.discovered_category_urls = unique
        marketplace.last_category_recon_at = datetime.now(tz=timezone.utc)
        marketplace.recon_frontier_state = None
        marketplace.category_resume_index = 0
        await self.db.flush()
        logger.info(
            "category_recon_done marketplace_id=%s listing_urls_found=%d",
            marketplace.id,
            len(unique),
        )
        return unique, False

    async def _phase2_product_harvest(
        self,
        marketplace: DimMarketplace,
        category_urls: list[str],
        *,
        start_index: int = 0,
        deadline_monotonic: float | None = None,
    ) -> tuple[int, int, bool]:
        """Phase 2: crawl each category URL, extract product links, save to pool.

        Processes a window of categories starting at start_index, capped at
        MAX_CATEGORY_URLS_PER_RUN entries.

        Convergence detection: if CATEGORY_CONVERGENCE_STREAK consecutive
        categories yield zero NEW persisted PDP, discovery exits early.

        Returns (total_saved, next_index, more_remaining) per the cursor
        state machine:
          - DEADLINE before/within absolute_idx → next_index = absolute_idx,
            more_remaining = True.
          - CONVERGENCE → next_index = 0, more_remaining = False.
          - WINDOW EXHAUSTED with end_index < total → next_index = end_index,
            more_remaining = True.
          - REACHED END (end_index >= total) → next_index = 0, more = False.
          - EMPTY WINDOW (start_index >= total, list shrank) →
            next_index = 0, more_remaining = False.

        next_index is an absolute index into category_urls. The incoming
        deadline is already headroom-adjusted by discover() — pass through
        unchanged.

        CRITICAL: next_index and more_remaining are INDEPENDENT signals.
        next_index==0 with more_remaining=True means "resume from index 0
        next run" (the very first category hit the deadline); it is NOT a
        completion signal. Completion is decided solely by
        more_remaining=False.
        """
        from app.modules.scraper.extractors import (
            detect_next_page,
            extract_links_from_repeated_structure,
            extract_product_links,
        )

        total_saved = 0
        empty_streak = 0
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

                _html, soup = await self.pool.scrape_page_for_analysis(
                    current_url,
                    static_fetch=True,
                )
                if soup is None:
                    break

                await self._emit_activity(
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
                    saved_this_call, _, save_exhausted = (
                        await self._save_product_urls(
                            marketplace.id,
                            product_urls,
                            deadline_monotonic=deadline_monotonic,
                        )
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

            # Deadline detected in the inner loop wins over convergence:
            # check before updating empty_streak / convergence.
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

        # Resolve final cursor per the state machine. This runs after the
        # loop in ALL cases. If the loop broke on a deadline,
        # more_remaining is already True and next_index already set, so
        # the first branch is a no-op. Otherwise resolve window-end vs
        # full-completion vs converged.
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

        return total_saved, next_index, more_remaining

    async def discover(
        self,
        marketplace: DimMarketplace,
        *,
        deadline_monotonic: float | None = None,
        parent_job_id: UUID | None = None,
        inner_job: ScrapeJob | None = None,
    ) -> DiscoveryResult:
        """Run discovery for one marketplace (ScrapeJob + listing crawl)."""
        started_perf = time.perf_counter()
        started_at = datetime.now(timezone.utc)
        errors: list[str] = []
        mp_id = marketplace.id
        domain = (marketplace.domain or "").strip()

        if inner_job is not None:
            # Orchestrator path (O2): tick pre-created this job as 'pending'
            # with parent_job_id and marketplace_id already set. Take
            # ownership without inserting a second row; do not overwrite the
            # tick-assigned linkage columns.
            job = inner_job
            job.status = "running"
            if job.started_at is None:
                job.started_at = started_at
            await self.db.commit()
            await self.db.refresh(job)
        else:
            job = ScrapeJob(
                job_type="discovery",
                marketplace_id=mp_id,
                parent_job_id=parent_job_id,
                status="running",
                started_at=started_at,
                config={"domain": domain},
            )
            self.db.add(job)
            await self.db.commit()
            await self.db.refresh(job)

        pages_scanned = 0
        candidate_urls_found = 0
        accepted_urls = 0
        duplicate_urls = 0
        rejected_urls = 0
        persisted_listings = 0
        status = "completed"
        completed_at: datetime | None = None

        try:
            settings = Settings()
            seed_url = (marketplace.base_url or f"https://{domain}").strip()
            if not seed_url.startswith("http"):
                seed_url = f"https://{seed_url}"
            if marketplace.base_url != seed_url:
                marketplace.base_url = seed_url

            current = await self.db.scalar(
                select(func.count(FactListing.id)).where(FactListing.marketplace_id == mp_id),
            )
            current_count = int(current or 0)
            quota = int(marketplace.product_quota or 0)
            no_quota_limit = max(int(settings.discovery_no_quota_limit or 200000), 1)
            # quota 0 = no explicit cap (large ceiling); quota > 0 = remaining slots
            remaining = max(0, quota - current_count) if quota > 0 else no_quota_limit

            sitemap_product_urls: list[str] = []
            if self._should_run_sitemap_harvest(marketplace):
                try:
                    sitemap_product_urls = await asyncio.wait_for(
                        self._phase0_sitemap_harvest(marketplace),
                        timeout=SITEMAP_PHASE_BUDGET_SECONDS,
                    )
                except asyncio.TimeoutError:
                    # Sitemap phase exhausted its budget. Treat as unavailable for
                    # this run, apply long cooldown, and fall through to category
                    # recon. We do NOT mark the whole discovery as failed — the
                    # marketplace may still be reachable via category crawl.
                    logger.warning(
                        "sitemap_harvest_timeout marketplace_id=%s budget_s=%s",
                        marketplace.id,
                        SITEMAP_PHASE_BUDGET_SECONDS,
                    )
                    errors.append("sitemap_phase_timeout")
                    now = datetime.now(tz=timezone.utc)
                    # Apply 24h cooldown by shifting last_sitemap_harvest_at into
                    # the past such that age < SITEMAP_STALE_DAYS but next retry
                    # waits SITEMAP_TIMEOUT_COOLDOWN_HOURS, not the normal
                    # SITEMAP_BAD_HARVEST_RETRY_HOURS.
                    retry_offset = timedelta(
                        days=SITEMAP_STALE_DAYS,
                        hours=-SITEMAP_TIMEOUT_COOLDOWN_HOURS,
                    )
                    marketplace.last_sitemap_harvest_at = now - retry_offset
                    await self.db.flush()
                    sitemap_product_urls = []

            products_found = 0
            partial_budget = False
            if len(sitemap_product_urls) >= SITEMAP_MIN_USEFUL_URLS:
                logger.info(
                    "discovery_using_sitemap marketplace_id=%s url_count=%d",
                    marketplace.id,
                    len(sitemap_product_urls),
                )
                candidate_urls_found = len(sitemap_product_urls)
                batch = sitemap_product_urls[:remaining]
                accepted_urls = len(batch)
                rejected_urls = max(0, len(sitemap_product_urls) - len(batch))
                start_offset = int(getattr(marketplace, "sitemap_resume_offset", 0) or 0)
                save_deadline = self._headroom_deadline(deadline_monotonic)
                new_count, next_offset, exhausted = await self._save_product_urls(
                    marketplace.id,
                    batch,
                    start_offset=start_offset,
                    deadline_monotonic=save_deadline,
                )
                products_found = new_count
                if exhausted and next_offset < len(batch):
                    marketplace.sitemap_resume_offset = next_offset
                    partial_budget = True
                else:
                    marketplace.sitemap_resume_offset = 0
                    partial_budget = False
                logger.info(
                    "discovery_sitemap_path marketplace_id=%s candidate=%d accepted=%d "
                    "saved=%d rejected=%d remaining=%d",
                    marketplace.id,
                    candidate_urls_found,
                    accepted_urls,
                    products_found,
                    rejected_urls,
                    remaining,
                )
                persisted_listings = products_found
                duplicate_urls = max(0, len(batch) - products_found)
                remaining = max(0, remaining - products_found)
                pages_scanned = 1 if sitemap_product_urls else 0
            else:
                block_deadline = self._headroom_deadline(deadline_monotonic)
                phase1_exhausted = False
                if self._should_run_category_recon(marketplace):
                    # phase1 writes discovered_category_urls itself on completion;
                    # on exhaust we deliberately ignore the partial listing list and
                    # skip phase2 this run.
                    _phase1_partial_urls, phase1_exhausted = (
                        await self._phase1_category_recon(
                            marketplace,
                            deadline_monotonic=block_deadline,
                        )
                    )
                if phase1_exhausted:
                    logger.info(
                        "discovery_category_path_phase1_exhausted marketplace_id=%s "
                        "remaining=%d",
                        marketplace.id,
                        remaining,
                    )
                    candidate_urls_found = 0
                    accepted_urls = 0
                    rejected_urls = 0
                    pages_scanned = 0
                    products_found = 0
                    persisted_listings = 0
                    duplicate_urls = 0
                    partial_budget = True
                else:
                    harvest_urls = [marketplace.base_url] + (marketplace.discovered_category_urls or [])
                    candidate_urls_found = len(harvest_urls)
                    accepted_urls = min(len(harvest_urls), remaining)
                    rejected_urls = max(0, len(harvest_urls) - accepted_urls)
                    pages_scanned = accepted_urls
                    # start_index indexes into the quota-trimmed list. When quota is
                    # finite and nearly exhausted, accepted_urls may shrink below
                    # start_index between runs → EMPTY WINDOW rule resets the cursor.
                    # This is intentional: quota is a hard ceiling and takes precedence
                    # over category-harvest completeness.
                    start_index = int(
                        getattr(marketplace, "category_resume_index", 0) or 0
                    )
                    products_found, next_index, phase2_more = (
                        await self._phase2_product_harvest(
                            marketplace,
                            harvest_urls[:accepted_urls],
                            start_index=start_index,
                            deadline_monotonic=block_deadline,
                        )
                    )
                    marketplace.category_resume_index = next_index
                    # Completion is decided by phase2_more (→ partial_budget), NOT by
                    # next_index. next_index==0 with phase2_more=True means "restart at
                    # 0 next run", not "done".
                    logger.info(
                        "discovery_category_path marketplace_id=%s candidate=%d accepted=%d "
                        "saved=%d rejected=%d remaining=%d",
                        marketplace.id,
                        candidate_urls_found,
                        accepted_urls,
                        products_found,
                        rejected_urls,
                        remaining,
                    )
                    persisted_listings = products_found
                    duplicate_urls = max(0, accepted_urls - products_found)
                    remaining = max(0, remaining - products_found)
                    if phase2_more:
                        partial_budget = True

            if partial_budget:
                status = "partial_budget"
            elif errors and persisted_listings > 0:
                status = "partial"
            elif errors:
                status = "error"
            elif candidate_urls_found == 0:
                status = "no_categories"
            else:
                status = "completed"

            completed_at = datetime.now(timezone.utc)
            if status == "error":
                job.status = "failed"
            elif status == "partial_budget":
                job.status = "partial"
            else:
                job.status = "completed"
            job.completed_at = completed_at
            job.duration_ms = int((time.perf_counter() - started_perf) * 1000)
            job.total_listings = candidate_urls_found
            job.successful = persisted_listings
            job.failed = len(errors)
            job.config = {
                "domain": domain,
                "pages_scanned": pages_scanned,
                "candidate_urls_found": candidate_urls_found,
                "accepted_urls": accepted_urls,
                "duplicate_urls": duplicate_urls,
                "rejected_urls": rejected_urls,
                "discovery_method": "category_crawl",
            }

            marketplace.last_discovery_at = completed_at
            marketplace.last_discovery_status = "failed" if status == "error" else status
            marketplace.last_discovery_products_found = persisted_listings

            pool_count = await self.db.scalar(
                select(func.count(FactListing.id)).where(
                    FactListing.marketplace_id == mp_id,
                    FactListing.is_active.is_(True),
                ),
            )
            marketplace.products_in_pool = int(pool_count or 0)

            await self.db.commit()
        except Exception as exc:
            logger.exception("Discovery failed for %s", mp_id)
            errors.append(str(exc))
            status = "error"
            completed_at = datetime.now(timezone.utc)
            job.status = "failed"
            job.completed_at = completed_at
            job.duration_ms = int((time.perf_counter() - started_perf) * 1000)
            job.total_listings = candidate_urls_found
            job.successful = persisted_listings
            job.failed = len(errors)
            job.config = {
                "domain": domain,
                "pages_scanned": pages_scanned,
                "candidate_urls_found": candidate_urls_found,
                "accepted_urls": accepted_urls,
                "duplicate_urls": duplicate_urls,
                "rejected_urls": rejected_urls,
                "discovery_method": "category_crawl",
            }
            marketplace.last_discovery_status = "failed"
            try:
                await self.db.commit()
            except Exception:
                await self.db.rollback()

        return DiscoveryResult(
            marketplace_id=mp_id,
            status=status,
            started_at=started_at,
            completed_at=completed_at,
            pages_scanned=pages_scanned,
            candidate_urls_found=candidate_urls_found,
            accepted_urls=accepted_urls,
            duplicate_urls=duplicate_urls,
            rejected_urls=rejected_urls,
            persisted_listings=persisted_listings,
            job_id=job.id,
            errors=errors,
            discovery_method="category_crawl",
        )
