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
import re
import time
from dataclasses import dataclass, field
from urllib.parse import urlparse

import structlog

from app.common.uuid7 import uuid7
from app.models.dimensions import DimMarketplace
from app.models.facts import FactListing
from app.modules.discovery.constants import SAVE_PRODUCT_URLS_BATCH_SIZE
from app.modules.discovery.gate_persist import PoolInsertDTO, write_pool_dtos_sync
from app.modules.persist.writer import (
    build_dim_product_fields,
    build_fact_listing_fields,
)
from app.modules.scraper.extractors import _looks_like_product_url
from app.modules.scraper.scraper_pool import ScraperPool, _sitemap_shard_priority

# Slug-style SKUs: a trailing (or dot-terminated) run of 3+ digits inside a
# dash-separated slug — techmart's `/baterii-ansmann-cr2016-1b-5020082`
# pattern, which `_looks_like_product_url` (path-segment oriented) misses.
_SLUG_SKU_RE = re.compile(r"-\d{3,}(?:[./]|$)")


def _url_is_product_like(path: str) -> bool:
    from app.common import html_parsing as _hp

    if _hp._use_rust():
        return _hp._rust_core.product_like_path(path)
    if _looks_like_product_url(path):
        return True
    return bool(_SLUG_SKU_RE.search(path.lower()))


def _url_hashes(urls: list[str]) -> list[str]:
    """url_hash for a whole shard in one call (Rust) — 150k URLs per shard."""
    from app.common import html_parsing as _hp

    if _hp._use_rust():
        return _hp._rust_core.url_hashes(urls)
    return [FactListing.compute_url_hash(u) for u in urls]

logger = logging.getLogger(__name__)
slog = structlog.get_logger(__name__)

# Onboarding caps: floors-not-ceilings policy — big enough for Rozetka-class
# catalogs, small enough to bound one task run. Overridable per call.
ENUMERATE_MAX_SUBFILES = 500
ENUMERATE_MAX_URLS = 500_000
_HASH_LOOKUP_CHUNK = 20_000


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
    # Category/listing pages seen in the same files (harvest optimisation
    # #3): the caller merges them into discovered_category_urls.
    category_urls: list[str] = field(default_factory=list)
    categories_added: int = 0
    # Sitemap <lastmod> coverage (harvest optimisation #6).
    lastmod_seen: int = 0
    lastmod_updated: int = 0


def _existing_hashes_sync(hashes: list[str]) -> dict[str, object]:
    """Chunked url_hash dedupe lookup on a short-lived sync session.

    Returns {url_hash: sitemap_lastmod} for the hashes already in the pool
    (the lastmod lets a re-scan spot what the shop says changed).
    """
    from sqlalchemy import bindparam, select
    from sqlalchemy import func as sa_func

    from app.database import sync_session_factory

    if not hashes:
        return {}
    db = sync_session_factory()
    try:
        found: dict[str, object] = {}
        # = ANY(array) is one bound parameter per chunk (an IN list binds one
        # parameter per hash: 5k placeholders to plan per query).
        for start in range(0, len(hashes), _HASH_LOOKUP_CHUNK):
            chunk = hashes[start : start + _HASH_LOOKUP_CHUNK]
            rows = db.execute(
                select(FactListing.url_hash, FactListing.sitemap_lastmod).where(
                    FactListing.url_hash == sa_func.any_(bindparam("hashes", expanding=False))
                ),
                {"hashes": chunk},
            )
            found.update({row[0]: row[1] for row in rows if row[0]})
        return found
    finally:
        db.close()


def parse_lastmod(raw: str | None):
    """Sitemap <lastmod> (W3C datetime: date or full ISO) -> aware UTC datetime."""
    from datetime import datetime, timezone

    if not raw:
        return None
    text = raw.strip()
    if not text:
        return None
    try:
        if len(text) == 10:
            return datetime.strptime(text, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        return None


def _write_lastmod_updates_sync(updates: list[tuple[str, object]]) -> int:
    """Gated fact_listing.sitemap_lastmod updates, pipelined like the
    matching engine's writes (chunk failure degrades to per-record)."""
    from sqlalchemy.exc import DBAPIError

    from app.database import sync_session_factory
    from app.modules.data_firewall.update_validator import authorize_scrape_update
    from app.modules.persist.gate_rpc import (
        GateRpcError,
        exec_write_record,
        exec_write_records,
    )
    from app.modules.persist.scrape_gate_fields import build_listing_update_fields

    signed = []
    for url_hash, lastmod in updates:
        outcome = authorize_scrape_update(
            table="fact_listing",
            kind="listing_sitemap_lastmod",
            fields=build_listing_update_fields(url_hash=url_hash, sitemap_lastmod=lastmod),
            reject_source="sitemap_enumerate",
        )
        if outcome.passed and outcome.signed_record is not None:
            signed.append(outcome.signed_record)
    if not signed:
        return 0
    written = 0
    db = sync_session_factory()
    try:
        for start in range(0, len(signed), 100):
            chunk = signed[start : start + 100]
            try:
                written += exec_write_records(db, chunk)
                db.commit()
            except (GateRpcError, DBAPIError):
                db.rollback()
                for record in chunk:
                    try:
                        written += exec_write_record(db, record)
                        db.commit()
                    except (GateRpcError, DBAPIError):
                        db.rollback()
        return written
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
    explicit_sitemaps: list[str] | None = None,
    publish_categories: bool = True,
) -> EnumerateResult:
    """Walk the full sitemap tree and gate-insert product URL skeletons.

    Category-like URLs met on the way are returned in the result and, when
    `publish_categories` is set, merged into discovered_category_urls right
    here (fan-out shards pass False and let the run finisher merge once).
    """
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
            category_urls=counts.get("category_urls", []),
            categories_added=counts.get("categories_added", 0),
            lastmod_seen=counts.get("lastmod_seen", 0),
            lastmod_updated=counts.get("lastmod_updated", 0),
        )

    from app.modules.discovery.sitemap_categories import collect_category_urls
    from app.modules.scraper.locale_selection import select_locale_url

    base_host = urlparse(marketplace.base_url).netloc.lower().removeprefix("www.")
    inserted = rejected = duplicates = 0
    raw_count = 0
    product_like_count = 0
    lastmod_seen = 0
    seen_in_run: set[str] = set()
    lastmod_updates: list[tuple[str, object]] = []
    category_urls: list[str] = []
    category_seen: set[str] = set()
    batch: list[PoolInsertDTO] = []
    write_task: asyncio.Task | None = None

    async def _flush() -> None:
        """Hand the batch to the writer thread; wait for the previous one
        first so at most one write is in flight while the next document
        fetches (streaming pipeline, optimisation #5)."""
        nonlocal inserted, rejected, batch, write_task
        if write_task is not None:
            result = await write_task
            inserted += result.inserted
            rejected += result.rejected
            write_task = None
        if batch:
            write_task = asyncio.create_task(asyncio.to_thread(write_pool_dtos_sync, batch))
            batch = []

    documents = 0
    try:
        async for shard_url, parsed in pool.walk_sitemaps(
            marketplace.base_url,
            explicit_sitemaps=explicit_sitemaps,
            max_subfiles=max_subfiles,
        ):
            documents += 1
            entries = parsed.get("url_entries", [])
            raw_count += len(entries)
            # --- classify: same-host product URLs + category-like pages ----
            doc_urls: list[str] = []
            doc_lastmod: dict[str, str] = {}
            shard_is_product = _sitemap_shard_priority(shard_url) == 0
            for entry in entries:
                loc = str(entry.get("loc") or "")
                if not loc:
                    continue
                alternates = entry.get("alternates")
                alt_map = alternates if isinstance(alternates, dict) else {}
                selected = select_locale_url(loc, alt_map, marketplace.locale)
                parsed_url = urlparse(selected)
                if parsed_url.netloc.lower().removeprefix("www.") != base_host:
                    continue
                if entry.get("lastmod"):
                    doc_lastmod[selected] = str(entry["lastmod"])
                if shard_is_product or _url_is_product_like(parsed_url.path):
                    doc_urls.append(selected)
                elif len(category_urls) < 2000 and selected not in category_seen:
                    for found in collect_category_urls([(selected, shard_url)], base_host):
                        if found not in category_seen:
                            category_seen.add(found)
                            category_urls.append(found)
            lastmod_seen += len(doc_lastmod)
            if not doc_urls:
                continue
            if raw_count > max_urls and product_like_count >= max_urls:
                # max_urls is a floor for the run; once met, stop walking.
                break
            product_like_count += len(doc_urls)
            # --- hash (Rust, one call) + dedupe against pool and this run --
            hashes = _url_hashes(doc_urls)
            existing = await asyncio.to_thread(_existing_hashes_sync, hashes)
            for url, url_hash in zip(doc_urls, hashes):
                if url_hash in existing or url_hash in seen_in_run:
                    duplicates += 1
                    if url_hash in existing:
                        new_lastmod = parse_lastmod(doc_lastmod.get(url))
                        if new_lastmod is not None and new_lastmod != existing[url_hash]:
                            lastmod_updates.append((url_hash, new_lastmod))
                    continue
                seen_in_run.add(url_hash)
                title = _title_from_url(url) or "product"
                # Time-ordered ids: 3.5x cheaper inserts on the 3 GB index set
                # (see app.common.uuid7).
                product_id = uuid7()
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
                            listing_id=uuid7(),
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
        await _flush()  # drain the last in-flight write
    except Exception as exc:
        slog.error(
            "sitemap_enumerate_fetch_failed",
            marketplace_id=str(marketplace_id),
            exc_type=type(exc).__name__,
        )
        return _result(f"error:{type(exc).__name__}")

    if documents == 0 or raw_count == 0:
        return _result("empty_sitemap")

    lastmod_updated = 0
    if lastmod_updates:
        lastmod_updated = await asyncio.to_thread(_write_lastmod_updates_sync, lastmod_updates)

    from app.modules.discovery.sitemap_categories import publish_category_urls

    categories_added = 0
    if publish_categories and category_urls:
        try:
            categories_added = await publish_category_urls(marketplace, category_urls)
        except Exception as exc:  # noqa: BLE001 - categories are a byproduct
            logger.warning(
                "sitemap_categories_publish_failed marketplace_id=%s err=%s",
                marketplace_id,
                exc,
            )

    result = _result(
        "completed",
        raw_urls=raw_count,
        product_like=product_like_count,
        inserted=inserted,
        rejected=rejected,
        duplicates=duplicates,
        category_urls=category_urls,
        categories_added=categories_added,
        lastmod_seen=lastmod_seen,
        lastmod_updated=lastmod_updated,
    )
    logger.info(
        "sitemap_enumerate_done marketplace_id=%s raw=%d product_like=%d "
        "inserted=%d duplicates=%d rejected=%d category_like=%d categories_added=%d "
        "lastmod_seen=%d lastmod_updated=%d duration_ms=%d",
        marketplace_id,
        result.raw_urls,
        result.product_like,
        result.inserted,
        result.duplicates,
        result.rejected,
        len(category_urls),
        categories_added,
        lastmod_seen,
        lastmod_updated,
        result.duration_ms,
    )
    return result
