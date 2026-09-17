"""Sitemap-full onboarding: enumerate a shop's ENTIRE product catalog cheaply.

SITEMAP_FIRST_PLAN slice 1. Unlike the pipeline's phase-0 harvest (sampled,
capped at 15 subfiles / 50k URLs, classify-gated with page fetches), this
path walks the whole sitemap tree with lifted caps and filters URLs
STRUCTURALLY ONLY (`_looks_like_product_url`) — zero page fetches per URL, so
onboarding a 100k-product shop costs tens of sitemap requests, not tens of
thousands of card fetches. Skeleton dim_product/fact_listing pairs go through
the same data_firewall gate path discovery uses (`write_pool_dtos_sync`);
prices arrive later from the list-page harvester (slice 2) or the card
scraper.

Idempotent by construction: dedupe against fact_listing.url_hash, so a rerun
only adds what a previous run missed — the resume cursor IS the pool.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from urllib.parse import urlparse
from uuid import uuid4

import structlog

from app.models.dimensions import DimMarketplace
from app.models.facts import FactListing
from app.modules.discovery.constants import SAVE_PRODUCT_URLS_BATCH_SIZE
from app.modules.discovery.gate_persist import PoolInsertDTO, write_pool_dtos_sync
from app.modules.persist.writer import (
    build_dim_product_fields,
    build_fact_listing_fields,
)
from app.modules.scraper.extractors import _looks_like_product_url
from app.modules.scraper.scraper_pool import ScraperPool

logger = logging.getLogger(__name__)
slog = structlog.get_logger(__name__)

# Onboarding caps: floors-not-ceilings policy — big enough for Rozetka-class
# catalogs, small enough to bound one task run. Overridable per call.
ENUMERATE_MAX_SUBFILES = 500
ENUMERATE_MAX_URLS = 500_000
_HASH_LOOKUP_CHUNK = 5_000


@dataclass(frozen=True)
class EnumerateResult:
    marketplace_id: str
    raw_urls: int
    product_like: int
    inserted: int
    rejected: int
    duplicates: int
    duration_ms: int
    status: str  # "completed" | "empty_sitemap" | "error:<type>"


def _existing_hashes_sync(hashes: list[str]) -> set[str]:
    """Chunked url_hash dedupe lookup on a short-lived sync session."""
    from sqlalchemy import select

    from app.database import sync_session_factory

    if not hashes:
        return set()
    db = sync_session_factory()
    try:
        found: set[str] = set()
        for start in range(0, len(hashes), _HASH_LOOKUP_CHUNK):
            chunk = hashes[start : start + _HASH_LOOKUP_CHUNK]
            rows = db.execute(
                select(FactListing.url_hash).where(FactListing.url_hash.in_(chunk))
            )
            found.update(row[0] for row in rows if row[0])
        return found
    finally:
        db.close()


def _title_from_url(url: str) -> str:
    path = urlparse(url).path.strip("/").split("/")[-1]
    if path:
        return path.replace("-", " ").replace("_", " ")[:500]
    return (url or "product")[:500]


def _normalize_name(name: str) -> str:
    return " ".join((name or "").lower().split())[:500]


async def enumerate_sitemap_full(
    marketplace: DimMarketplace,
    pool: ScraperPool,
    *,
    max_subfiles: int = ENUMERATE_MAX_SUBFILES,
    max_urls: int = ENUMERATE_MAX_URLS,
) -> EnumerateResult:
    """Walk the full sitemap tree and gate-insert product URL skeletons."""
    started = time.perf_counter()
    marketplace_id = marketplace.id

    def _result(status: str, **counts) -> EnumerateResult:
        return EnumerateResult(
            marketplace_id=str(marketplace_id),
            raw_urls=counts.get("raw_urls", 0),
            product_like=counts.get("product_like", 0),
            inserted=counts.get("inserted", 0),
            rejected=counts.get("rejected", 0),
            duplicates=counts.get("duplicates", 0),
            duration_ms=int((time.perf_counter() - started) * 1000),
            status=status,
        )

    try:
        raw_urls = await pool.fetch_sitemap_candidates(
            marketplace.base_url,
            marketplace_locale=marketplace.locale,
            max_subfiles=max_subfiles,
            max_urls=max_urls,
        )
    except Exception as exc:
        slog.error(
            "sitemap_enumerate_fetch_failed",
            marketplace_id=str(marketplace_id),
            exc_type=type(exc).__name__,
        )
        return _result(f"error:{type(exc).__name__}")

    if not raw_urls:
        return _result("empty_sitemap")

    base_host = urlparse(marketplace.base_url).netloc.lower().removeprefix("www.")
    product_urls: list[str] = []
    for url in raw_urls:
        parsed = urlparse(url)
        if parsed.netloc.lower().removeprefix("www.") != base_host:
            continue
        if _looks_like_product_url(parsed.path):
            product_urls.append(url)

    hash_by_url = {url: FactListing.compute_url_hash(url) for url in product_urls}
    existing = await asyncio.to_thread(
        _existing_hashes_sync, list(hash_by_url.values())
    )

    inserted = rejected = duplicates = 0
    batch: list[PoolInsertDTO] = []
    seen_in_run: set[str] = set()

    async def _flush() -> None:
        nonlocal inserted, rejected, batch
        if not batch:
            return
        result = await asyncio.to_thread(write_pool_dtos_sync, batch)
        inserted += result.inserted
        rejected += result.rejected
        batch = []

    for url in product_urls:
        url_hash = hash_by_url[url]
        if url_hash in existing or url_hash in seen_in_run:
            duplicates += 1
            continue
        seen_in_run.add(url_hash)
        title = _title_from_url(url) or "product"
        product_id = uuid4()
        batch.append(
            PoolInsertDTO(
                marketplace_id=marketplace_id,
                dim_product=build_dim_product_fields(
                    product_id=product_id,
                    name=title,
                    name_normalized=_normalize_name(title) or "product",
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
            )
        )
        if len(batch) >= SAVE_PRODUCT_URLS_BATCH_SIZE:
            await _flush()

    await _flush()

    result = _result(
        "completed",
        raw_urls=len(raw_urls),
        product_like=len(product_urls),
        inserted=inserted,
        rejected=rejected,
        duplicates=duplicates,
    )
    logger.info(
        "sitemap_enumerate_done marketplace_id=%s raw=%d product_like=%d "
        "inserted=%d duplicates=%d rejected=%d duration_ms=%d",
        marketplace_id,
        result.raw_urls,
        result.product_like,
        result.inserted,
        result.duplicates,
        result.rejected,
        result.duration_ms,
    )
    return result
