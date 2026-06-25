"""ScrapeLog terminal status → honest outcome bucket mapping (pure logic)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import structlog

slog = structlog.get_logger(__name__)

BUCKET_SUCCESSFUL = "successful"
BUCKET_UNCHANGED = "unchanged"
BUCKET_FILTERED = "filtered"
BUCKET_FAILED = "failed"

TERMINAL_SUCCESSFUL = frozenset({"success"})
TERMINAL_UNCHANGED = frozenset({"no_change"})
TERMINAL_FILTERED = frozenset({"not_a_product"})
TERMINAL_FAILED = frozenset(
    {
        "error",
        "timeout",
        "blocked",
        "captcha",
        "not_found",
        "price_not_found",
        "parse_error",
        "currency_rejected",
        "missing_critical_data",
        "technical_error",
        "fetch_failed",
        "parse_failed",
        "quota_exceeded",
        "persist_failed",
    }
)

ALL_KNOWN_TERMINAL_STATUSES = (
    TERMINAL_SUCCESSFUL | TERMINAL_UNCHANGED | TERMINAL_FILTERED | TERMINAL_FAILED
)

# Single source of truth for scrape_logs.status CHECK repair and bucket classification.
# Must match migration 024_reject_data_and_not_a_product (_STATUSES_WITH_NOT_A_PRODUCT).
CANONICAL_SCRAPE_LOG_STATUSES: tuple[str, ...] = tuple(sorted(ALL_KNOWN_TERMINAL_STATUSES))

def empty_outcome_buckets() -> dict[str, int]:
    """Return a zeroed four-bucket dict plus ``total``."""
    return {
        BUCKET_SUCCESSFUL: 0,
        BUCKET_UNCHANGED: 0,
        BUCKET_FILTERED: 0,
        BUCKET_FAILED: 0,
        "total": 0,
    }


def classify_scrape_log_status(status: str) -> str | None:
    """Map one ScrapeLog.status value to an outcome bucket name, or None if unknown."""
    if status in TERMINAL_SUCCESSFUL:
        return BUCKET_SUCCESSFUL
    if status in TERMINAL_UNCHANGED:
        return BUCKET_UNCHANGED
    if status in TERMINAL_FILTERED:
        return BUCKET_FILTERED
    if status in TERMINAL_FAILED:
        return BUCKET_FAILED
    return None


def accumulate_status_count(
    buckets: dict[str, int],
    status: str,
    count: int,
    *,
    job_id: UUID | None = None,
    marketplace_id: UUID | None = None,
) -> None:
    """Add *count* into the correct bucket; warn and skip when status is unknown."""
    bucket = classify_scrape_log_status(status)
    if bucket is None:
        slog.warning(
            "scrape_log_status_unclassified",
            status=status,
            count=int(count),
            job_id=str(job_id) if job_id is not None else None,
            marketplace_id=str(marketplace_id) if marketplace_id is not None else None,
        )
        return
    buckets[bucket] = int(buckets.get(bucket, 0)) + int(count)


def finalize_outcome_buckets(buckets: dict[str, int]) -> dict[str, int]:
    """Compute ``total`` from the four explicit buckets."""
    buckets["total"] = (
        int(buckets.get(BUCKET_SUCCESSFUL, 0))
        + int(buckets.get(BUCKET_UNCHANGED, 0))
        + int(buckets.get(BUCKET_FILTERED, 0))
        + int(buckets.get(BUCKET_FAILED, 0))
    )
    return buckets


def aggregate_marketplace_log_rows(
    rows: list[Any],
    *,
    job_id: UUID | None = None,
) -> dict[UUID, dict[str, int]]:
    """Group (marketplace_id, status, count) rows into per-MP outcome buckets."""
    by_marketplace: dict[UUID, dict[str, int]] = {}
    for row in rows:
        marketplace_id = row.marketplace_id
        status = str(row.status)
        count = int(row.count or 0)
        if marketplace_id not in by_marketplace:
            by_marketplace[marketplace_id] = empty_outcome_buckets()
        accumulate_status_count(
            by_marketplace[marketplace_id],
            status,
            count,
            job_id=job_id,
            marketplace_id=marketplace_id,
        )
    for buckets in by_marketplace.values():
        finalize_outcome_buckets(buckets)
    return by_marketplace


def sum_buckets_across_marketplaces(
    buckets_by_marketplace: dict[UUID, dict[str, int]],
) -> dict[str, int]:
    """Sum per-marketplace buckets into one run-wide totals dict."""
    totals = empty_outcome_buckets()
    for buckets in buckets_by_marketplace.values():
        for key in (BUCKET_SUCCESSFUL, BUCKET_UNCHANGED, BUCKET_FILTERED, BUCKET_FAILED):
            totals[key] += int(buckets.get(key, 0))
    return finalize_outcome_buckets(totals)
