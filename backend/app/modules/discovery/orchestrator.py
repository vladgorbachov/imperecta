"""Discovery orchestrator: DimMarketplace → listing pages → DimProduct + FactListing."""

import asyncio
import logging
import random
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlparse
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models.app_tables import ScrapeJob
from app.models.dimensions import DimMarketplace
from app.models.facts import FactListing
from app.modules.discovery import (
    bfs_walker,
    budget_governor,
    category_processor,
    classifier_adapter,
    cursor_store,
    fetch_adapter,
    sitemap_harvester,
    url_canonicalizer,
)
from app.modules.discovery.constants import (
    CATEGORY_RECON_STALE_DAYS,
    SAVE_BUDGET_HEADROOM_FRACTION,
    SAVE_PRODUCT_URLS_BATCH_SIZE,
    SITEMAP_CLASSIFY_CONCURRENCY,
    SITEMAP_FULL_CLASSIFY_LIMIT,
    SITEMAP_MIN_USEFUL_URLS,
    SITEMAP_PHASE_BUDGET_SECONDS,
    SITEMAP_REJECT_THRESHOLD,
    SITEMAP_SAMPLE_SIZE,
    SITEMAP_STALE_DAYS,
    SITEMAP_TIMEOUT_COOLDOWN_HOURS,
)
from app.modules.discovery.gate_persist import (
    PoolInsertDTO,
    PoolWriteResult,
    write_pool_dtos_sync,
)
from app.modules.persist.meta_write import (
    build_dim_marketplace_fields,
    build_scrape_job_fields,
    write_meta_async,
)
from app.modules.discovery.alerting import (
    emit_canonical_missing_rate_high_if_needed,
    emit_classify_unknown_rate_high_if_needed,
    emit_discovery_service_alert,
)
from app.modules.persist.writer import (
    build_dim_product_fields,
    build_fact_listing_fields,
)
from app.modules.scraper.locale_selection import build_accept_language_header
from app.modules.scraper.scraper_pool import ScraperPool

import structlog

logger = logging.getLogger(__name__)
slog = structlog.get_logger(__name__)


async def _meta_update_marketplace_snapshot(marketplace: DimMarketplace) -> None:
    columns = cursor_store.snapshot_meta_columns(marketplace)
    await write_meta_async(
        table="dim_marketplace",
        operation="update",
        fields=build_dim_marketplace_fields(id=marketplace.id, **columns),
        reject_source="discovery",
    )


async def _success_meta_snapshot_with_retry(
    marketplace: DimMarketplace,
    *,
    job_id: UUID,
    status: str,
    persisted_listings: int,
) -> None:
    """Success-path snapshot write with one retry; alert and swallow on double failure."""
    last_exc: Exception | None = None
    for attempt in (1, 2):
        try:
            await _meta_update_marketplace_snapshot(marketplace)
            return
        except Exception as exc:
            last_exc = exc
            if attempt == 1:
                slog.warning(
                    "discovery_meta_snapshot_write_retry",
                    marketplace_id=str(marketplace.id),
                    job_id=str(job_id),
                    attempt=attempt,
                    exc_type=type(exc).__name__,
                )
    await emit_discovery_service_alert(
        "orchestrator",
        "critical",
        "meta_snapshot_write_failed",
        (
            f"Marketplace snapshot write failed after retry "
            f"marketplace_id={marketplace.id}"
        ),
        marketplace_id=marketplace.id,
        context={
            "job_id": str(job_id),
            "status": status,
            "persisted_listings": persisted_listings,
            "write_target": "dim_marketplace",
        },
    )
    slog.error(
        "discovery_meta_snapshot_write_failed",
        marketplace_id=str(marketplace.id),
        job_id=str(job_id),
        status=status,
        persisted_listings=persisted_listings,
        exc_type=type(last_exc).__name__ if last_exc else "Exception",
    )


async def _emit_discover_status_inconsistent_if_needed(
    *,
    marketplace_id: UUID,
    status: str,
    persisted_listings: int,
    candidate_urls_found: int,
    accepted_urls: int,
) -> None:
    """Defensive alert when assembled status contradicts persisted counters."""
    if persisted_listings > 0 and status == "no_categories":
        await emit_discovery_service_alert(
            "orchestrator",
            "warning",
            "discover_status_inconsistent",
            (
                f"Discovery status inconsistent marketplace_id={marketplace_id} "
                f"status={status} persisted_listings={persisted_listings}"
            ),
            marketplace_id=marketplace_id,
            context={
                "status": status,
                "persisted_listings": persisted_listings,
                "candidate_urls_found": candidate_urls_found,
                "accepted_urls": accepted_urls,
            },
        )


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


class DiscoveryOrchestrator:
    """Orchestrate marketplace discovery: sitemap harvest, category BFS, product harvest."""

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

    async def _write_pool_batch(
        self,
        marketplace_id: UUID,
        batch_dtos: list[PoolInsertDTO],
    ) -> PoolWriteResult:
        """Run gated pool write; alert on total reject or commit failure."""
        batch_size = len(batch_dtos)
        try:
            result = await asyncio.to_thread(write_pool_dtos_sync, batch_dtos)
        except Exception as exc:
            await emit_discovery_service_alert(
                "gate_persist",
                "error",
                "pool_batch_commit_failed",
                f"Pool batch commit failed marketplace_id={marketplace_id}",
                marketplace_id=marketplace_id,
                context={
                    "batch_size": batch_size,
                    "exc_type": type(exc).__name__,
                },
            )
            slog.error(
                "discovery_pool_batch_commit_failed",
                marketplace_id=str(marketplace_id),
                batch_size=batch_size,
                exc_type=type(exc).__name__,
            )
            raise

        if (
            batch_size > 0
            and result.inserted == 0
            and result.rejected == batch_size
        ):
            await emit_discovery_service_alert(
                "gate_persist",
                "warning",
                "pool_batch_total_reject",
                (
                    f"Pool batch total reject marketplace_id={marketplace_id} "
                    f"batch_size={batch_size}"
                ),
                marketplace_id=marketplace_id,
                context={
                    "batch_size": batch_size,
                    "inserted": result.inserted,
                    "rejected": result.rejected,
                },
            )
            slog.warning(
                "discovery_pool_batch_total_reject",
                marketplace_id=str(marketplace_id),
                batch_size=batch_size,
                inserted=result.inserted,
                rejected=result.rejected,
            )

        return result

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
        hash_by_url = {url: url_canonicalizer.url_hash(url) for url in normalized_urls}
        hash_count = len(hash_by_url)
        try:
            existing_hashes = await url_canonicalizer.load_existing_url_hashes(
                self.db,
                list(hash_by_url.values()),
            )
        except Exception as exc:
            await emit_discovery_service_alert(
                "url_canonicalizer",
                "error",
                "dedup_lookup_failed",
                f"Dedup lookup failed marketplace_id={marketplace_id}",
                marketplace_id=marketplace_id,
                context={
                    "hash_count": hash_count,
                    "exc_type": type(exc).__name__,
                },
            )
            slog.error(
                "discovery_dedup_lookup_failed",
                marketplace_id=str(marketplace_id),
                hash_count=hash_count,
                exc_type=type(exc).__name__,
            )
            existing_hashes = set()

        new_count = 0
        pending_in_batch = 0
        batch_dtos: list[PoolInsertDTO] = []
        for relative_index, url in enumerate(normalized_urls):
            url_hash = hash_by_url[url]
            if url_hash in existing_hashes:
                continue

            title = _title_from_url(url) or "product"
            product_id = uuid4()
            name_normalized = _normalize_name(title) or "product"
            batch_dtos.append(
                PoolInsertDTO(
                    marketplace_id=marketplace_id,
                    dim_product=build_dim_product_fields(
                        product_id=product_id,
                        name=title,
                        name_normalized=name_normalized,
                        is_active=True,
                    ),
                    fact_listing=build_fact_listing_fields(
                        product_id=product_id,
                        marketplace_id=marketplace_id,
                        external_url=url,
                        url_hash=url_hash,
                        is_active=True,
                        page_role="product",
                    ),
                ),
            )
            existing_hashes.add(url_hash)
            pending_in_batch += 1

            if pending_in_batch >= SAVE_PRODUCT_URLS_BATCH_SIZE:
                write_result = await self._write_pool_batch(
                    marketplace_id,
                    batch_dtos,
                )
                new_count += write_result.inserted
                batch_dtos = []
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

        if batch_dtos:
            write_result = await self._write_pool_batch(
                marketplace_id,
                batch_dtos,
            )
            new_count += write_result.inserted
        return new_count, start_offset + len(normalized_urls), False

    def _should_run_sitemap_harvest(self, marketplace: DimMarketplace) -> bool:
        """Return True if sitemap harvest should run."""
        if cursor_store.get_sitemap_resume_offset(marketplace) > 0:
            return True
        if cursor_store.get_last_sitemap_harvest_at(marketplace) is None:
            return True
        age = (
            datetime.now(tz=timezone.utc)
            - cursor_store.get_last_sitemap_harvest_at(marketplace)
        ).days
        return age >= SITEMAP_STALE_DAYS

    async def _classify_and_resolve_url(
        self,
        url: str,
        *,
        requires_js: bool,
        scrape_tier: int,
        marketplace_locale: str | None,
        accept_language: str | None,
    ) -> tuple[str, str, bool | None]:
        """Fetch, resolve canonical URL, and return (page_role, pool_url, canonical_flag).

        canonical_flag is None when fetch/soup failed; True when soup lacked canonical;
        False when a canonical link was resolved.
        """
        try:
            _html, soup = await fetch_adapter.fetch_page(
                self.pool,
                url,
                requires_js=requires_js,
                scrape_tier=scrape_tier,
                accept_language=accept_language,
            )
        except Exception:
            return "unknown", url, None
        if soup is None:
            return "unknown", url, None
        try:
            canonical = url_canonicalizer.canonical_from_soup(soup, url)
            pool_url = url_canonicalizer.pool_url(canonical, url)
            role = classifier_adapter.classify_page_role(soup, pool_url)
            return role, pool_url, canonical is None
        except Exception:
            return "unknown", url, None

    async def _filter_urls_by_role(
        self,
        urls: list[str],
        *,
        requires_js: bool,
        scrape_tier: int,
        marketplace_locale: str | None = None,
        marketplace_id: UUID | None = None,
    ) -> tuple[list[str], dict[str, int | float | str | None]]:
        """Classify every candidate URL structurally; admit only page_role=product.

        Large lists may use a sample for early reject_sample (source not product-
        oriented), but every admitted URL is individually classified. The former
        trust_sample blind-accept path is removed.

        Concurrency is bounded by SITEMAP_CLASSIFY_CONCURRENCY.
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

        accept_language = build_accept_language_header(marketplace_locale)
        semaphore = asyncio.Semaphore(SITEMAP_CLASSIFY_CONCURRENCY)

        async def classify_one(
            target_url: str,
        ) -> tuple[str, str, str, bool | None]:
            async with semaphore:
                role, pool_url, canonical_flag = await self._classify_and_resolve_url(
                    target_url,
                    requires_js=requires_js,
                    scrape_tier=scrape_tier,
                    marketplace_locale=marketplace_locale,
                    accept_language=accept_language,
                )
                return target_url, role, pool_url, canonical_flag

        async def _emit_classifier_gate_defence_alerts_if_needed(
            results: list[tuple[str, str, str, bool | None]],
            mode: str,
        ) -> None:
            if marketplace_id is None:
                return
            soup_classified = sum(
                1 for _source, _role, _pool, flag in results if flag is not None
            )
            canonical_missing = sum(
                1 for _source, _role, _pool, flag in results if flag is True
            )
            await emit_canonical_missing_rate_high_if_needed(
                marketplace_id=marketplace_id,
                classified=soup_classified,
                canonical_missing=canonical_missing,
            )
            classified = len(results)
            unknown_count = sum(
                1 for _source, role, _pool, flag in results
                if flag is not None and role == "unknown"
            )
            await emit_classify_unknown_rate_high_if_needed(
                marketplace_id=marketplace_id,
                classified=classified,
                unknown_count=unknown_count,
                mode=mode,
            )

        def _products_from_results(
            results: list[tuple[str, str, str, bool | None]],
        ) -> list[str]:
            seen_hashes: set[str] = set()
            accepted: list[str] = []
            for _source_url, role, pool_url, _canonical_flag in results:
                if role != "product":
                    continue
                url_hash = url_canonicalizer.url_hash(pool_url)
                if url_hash in seen_hashes:
                    continue
                seen_hashes.add(url_hash)
                accepted.append(pool_url)
            return accepted

        def _log_gate(
            results: list[tuple[str, str, str, bool | None]],
            accepted: list[str],
        ) -> None:
            kept = len(accepted)
            rejected = sum(1 for _s, role, _p, _f in results if role != "product")
            logger.info(
                "discovery_gate_classified total=%d kept_product=%d rejected_nonproduct=%d",
                len(results),
                kept,
                rejected,
            )

        if len(urls) <= SITEMAP_FULL_CLASSIFY_LIMIT:
            stats["mode"] = "full"
            results = await asyncio.gather(*(classify_one(u) for u in urls))
            stats["classified"] = len(results)
            accepted = _products_from_results(results)
            stats["accepted"] = len(accepted)
            _log_gate(results, accepted)
            await _emit_classifier_gate_defence_alerts_if_needed(results, "full")
            return accepted, stats

        sample_size = min(SITEMAP_SAMPLE_SIZE, len(urls))
        sample = random.sample(urls, sample_size)
        sample_results = await asyncio.gather(*(classify_one(u) for u in sample))
        stats["sampled"] = len(sample_results)
        product_in_sample = sum(
            1 for _u, role, _p, _f in sample_results if role == "product"
        )
        ratio = product_in_sample / len(sample_results) if sample_results else 0.0
        stats["sample_product_ratio"] = round(ratio, 3)

        if ratio < SITEMAP_REJECT_THRESHOLD:
            stats["mode"] = "reject_sample"
            accepted = _products_from_results(sample_results)
            stats["classified"] = len(sample_results)
            stats["accepted"] = len(accepted)
            _log_gate(sample_results, accepted)
            await _emit_classifier_gate_defence_alerts_if_needed(
                sample_results,
                "reject_sample",
            )
            return accepted, stats

        sample_urls_set = {source for source, _role, _pool, _f in sample_results}
        remaining = [u for u in urls if u not in sample_urls_set]
        remaining_results = await asyncio.gather(*(classify_one(u) for u in remaining))
        all_results = list(sample_results) + list(remaining_results)
        stats["mode"] = "full_large"
        stats["classified"] = len(all_results)
        accepted = _products_from_results(all_results)
        stats["accepted"] = len(accepted)
        _log_gate(all_results, accepted)
        await _emit_classifier_gate_defence_alerts_if_needed(all_results, "full_large")
        return accepted, stats

    def _should_run_category_recon(self, marketplace: DimMarketplace) -> bool:
        """Return True if category recon should run."""
        if cursor_store.get_category_resume_index(marketplace) > 0:
            return False
        if cursor_store.load_frontier_state(marketplace):
            return True
        if not cursor_store.get_discovered_category_urls(marketplace):
            return True
        if cursor_store.get_last_category_recon_at(marketplace) is None:
            return True
        age = (
            datetime.now(tz=timezone.utc)
            - cursor_store.get_last_category_recon_at(marketplace)
        ).days
        return age >= CATEGORY_RECON_STALE_DAYS

    async def _resolve_category_backlog(self, marketplace: DimMarketplace) -> bool:
        """Resolve effective category backlog; emit service alert on detector divergence.

        Primary: resume_index < len(discovered_category_urls) — unfinished Phase 2 work.
        Binary redundancy: len(discovered_category_urls) > 0 — coarse backlog signal.
        On divergence, write a service alert and use the binary (redundancy) value.
        """
        discovered_urls = cursor_store.get_discovered_category_urls(marketplace)
        resume_index = cursor_store.get_category_resume_index(marketplace)
        categories_len = len(discovered_urls)
        if resume_index > categories_len:
            await emit_discovery_service_alert(
                "cursor_store",
                "warning",
                "resume_index_oob",
                (
                    f"Category resume index out of range "
                    f"marketplace_id={marketplace.id}"
                ),
                marketplace_id=marketplace.id,
                context={
                    "resume_index": resume_index,
                    "categories_len": categories_len,
                },
            )
            slog.warning(
                "discovery_resume_index_oob",
                marketplace_id=str(marketplace.id),
                resume_index=resume_index,
                categories_len=categories_len,
            )
        primary = resume_index < categories_len
        binary = categories_len > 0
        if primary != binary:
            context = {
                "resume_index": resume_index,
                "categories_len": categories_len,
            }
            message = (
                f"Category backlog detector divergence "
                f"marketplace_id={marketplace.id} "
                f"resume_index={resume_index} categories_len={categories_len}"
            )
            slog.warning(
                "discovery_budget_governor_detector_divergence",
                marketplace_id=str(marketplace.id),
                resume_index=resume_index,
                categories_len=categories_len,
                primary=primary,
                binary=binary,
            )
            await emit_discovery_service_alert(
                "budget_governor",
                "warning",
                "resume_index_desync",
                message,
                marketplace_id=marketplace.id,
                context=context,
            )
            return binary
        return primary

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
            job = inner_job
            job_columns: dict[str, Any] = {"status": "running"}
            if job.started_at is None:
                job_columns["started_at"] = started_at
            await write_meta_async(
                table="scrape_jobs",
                operation="update",
                fields=build_scrape_job_fields(id=job.id, **job_columns),
                reject_source="discovery",
            )
            await self.db.refresh(job)
        else:
            job_id = uuid4()
            await write_meta_async(
                table="scrape_jobs",
                operation="insert",
                fields=build_scrape_job_fields(
                    id=job_id,
                    job_type="discovery",
                    marketplace_id=mp_id,
                    parent_job_id=parent_job_id,
                    status="running",
                    started_at=started_at,
                    config={"domain": domain},
                ),
                reject_source="discovery",
            )
            job = await self.db.get(ScrapeJob, job_id)
            if job is None:
                raise RuntimeError(f"discovery job not found after insert: {job_id}")

        pages_scanned = 0
        candidate_urls_found = 0
        accepted_urls = 0
        duplicate_urls = 0
        rejected_urls = 0
        persisted_listings = 0
        status = "completed"
        completed_at: datetime | None = None
        discovery_phase = "init"

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
                discovery_phase = "sitemap_harvest"
                await self._emit_activity(
                    f"discovery sitemap harvest start "
                    f"domain={marketplace.domain or marketplace.base_url}"
                )
                try:
                    sitemap_product_urls = await asyncio.wait_for(
                        sitemap_harvester.harvest_sitemap(
                            marketplace,
                            self.pool,
                            self.db,
                            filter_urls_by_role=self._filter_urls_by_role,
                            on_activity=self._emit_activity,
                        ),
                        timeout=SITEMAP_PHASE_BUDGET_SECONDS,
                    )
                    await self._emit_activity(
                        f"discovery sitemap harvest done raw="
                        f"{len(sitemap_product_urls)} useful="
                        f"{len(sitemap_product_urls) >= SITEMAP_MIN_USEFUL_URLS}"
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
                    # sitemap_harvester bad-harvest retry window.
                    retry_offset = timedelta(
                        days=SITEMAP_STALE_DAYS,
                        hours=-SITEMAP_TIMEOUT_COOLDOWN_HOURS,
                    )
                    cursor_store.set_last_sitemap_harvest_at(
                        marketplace,
                        now - retry_offset,
                    )
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
                start_offset = cursor_store.get_sitemap_resume_offset(marketplace)
                save_deadline = self._headroom_deadline(deadline_monotonic)
                new_count, next_offset, exhausted = await self._save_product_urls(
                    marketplace.id,
                    batch,
                    start_offset=start_offset,
                    deadline_monotonic=save_deadline,
                )
                products_found = new_count
                if exhausted and next_offset < len(batch):
                    cursor_store.set_sitemap_resume_offset(marketplace, next_offset)
                    partial_budget = True
                else:
                    cursor_store.set_sitemap_resume_offset(marketplace, 0)
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
                has_backlog = await self._resolve_category_backlog(marketplace)
                phase1_deadline, phase2_deadline = budget_governor.allocate(
                    block_deadline,
                    has_backlog,
                )
                phase1_exhausted = False
                if self._should_run_category_recon(marketplace):
                    discovery_phase = "category_bfs"
                    _, phase1_exhausted = await bfs_walker.run_category_bfs(
                        marketplace,
                        self.pool,
                        self.db,
                        deadline_monotonic=phase1_deadline,
                        on_activity=self._emit_activity,
                    )
                if phase1_exhausted and not has_backlog:
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
                    discovery_phase = "category_harvest"
                    harvest_urls = [marketplace.base_url] + (
                        cursor_store.get_discovered_category_urls(marketplace)
                    )
                    candidate_urls_found = len(harvest_urls)
                    accepted_urls = min(len(harvest_urls), remaining)
                    rejected_urls = max(0, len(harvest_urls) - accepted_urls)
                    pages_scanned = accepted_urls
                    start_index = cursor_store.get_category_resume_index(marketplace)
                    products_found, next_index, phase2_more = (
                        await category_processor.run_product_harvest(
                            marketplace,
                            self.pool,
                            self.db,
                            harvest_urls[:accepted_urls],
                            start_index=start_index,
                            deadline_monotonic=phase2_deadline,
                            on_activity=self._emit_activity,
                            filter_urls_by_role=self._filter_urls_by_role,
                            save_product_urls=self._save_product_urls,
                        )
                    )
                    cursor_store.set_category_resume_index(marketplace, next_index)
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

            await _emit_discover_status_inconsistent_if_needed(
                marketplace_id=mp_id,
                status=status,
                persisted_listings=persisted_listings,
                candidate_urls_found=candidate_urls_found,
                accepted_urls=accepted_urls,
            )

            discovery_phase = "finalize"
            completed_at = datetime.now(timezone.utc)
            if status == "error":
                job_status = "failed"
            elif status == "partial_budget":
                job_status = "partial"
            else:
                job_status = "completed"
            job_config = {
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

            finalize_result = await write_meta_async(
                table="scrape_jobs",
                operation="update",
                fields=build_scrape_job_fields(
                    id=job.id,
                    status=job_status,
                    completed_at=completed_at,
                    duration_ms=int((time.perf_counter() - started_perf) * 1000),
                    total_listings=candidate_urls_found,
                    successful=persisted_listings,
                    failed=len(errors),
                    config=job_config,
                ),
                reject_source="discovery",
            )
            if not finalize_result.ok:
                await emit_discovery_service_alert(
                    "orchestrator",
                    "error",
                    "finalize_write_rejected",
                    (
                        f"Discovery finalize scrape_jobs update rejected "
                        f"marketplace_id={mp_id}"
                    ),
                    marketplace_id=mp_id,
                    context={
                        "job_id": str(job.id),
                        "status": status,
                        "job_status": job_status,
                        "failed_count": len(errors),
                    },
                )
                slog.error(
                    "discovery_finalize_write_rejected",
                    marketplace_id=str(mp_id),
                    job_id=str(job.id),
                    status=status,
                    job_status=job_status,
                    failed_count=len(errors),
                )
            await _success_meta_snapshot_with_retry(
                marketplace,
                job_id=job.id,
                status=status,
                persisted_listings=persisted_listings,
            )
        except Exception as exc:
            logger.exception("Discovery failed for %s", mp_id)
            await emit_discovery_service_alert(
                "orchestrator",
                "error",
                "discover_exception",
                f"Discovery failed marketplace_id={mp_id}",
                marketplace_id=mp_id,
                context={
                    "job_id": str(job.id),
                    "phase": discovery_phase,
                    "exc_type": type(exc).__name__,
                    "status": "error",
                },
            )
            errors.append(str(exc))
            status = "error"
            completed_at = datetime.now(timezone.utc)
            job_config = {
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
                await write_meta_async(
                    table="scrape_jobs",
                    operation="update",
                    fields=build_scrape_job_fields(
                        id=job.id,
                        status="failed",
                        completed_at=completed_at,
                        duration_ms=int((time.perf_counter() - started_perf) * 1000),
                        total_listings=candidate_urls_found,
                        successful=persisted_listings,
                        failed=len(errors),
                        config=job_config,
                    ),
                    reject_source="discovery",
                )
                await _meta_update_marketplace_snapshot(marketplace)
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
