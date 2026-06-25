"""Pure-logic tests for ScrapeLog → outcome bucket mapping."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from app.modules.scraper.pipeline.outcome_buckets import (
    ALL_KNOWN_TERMINAL_STATUSES,
    BUCKET_FAILED,
    BUCKET_FILTERED,
    BUCKET_SUCCESSFUL,
    BUCKET_UNCHANGED,
    CANONICAL_SCRAPE_LOG_STATUSES,
    TERMINAL_FAILED,
    TERMINAL_FILTERED,
    TERMINAL_SUCCESSFUL,
    TERMINAL_UNCHANGED,
    aggregate_marketplace_log_rows,
    classify_scrape_log_status,
    empty_outcome_buckets,
    sum_buckets_across_marketplaces,
)


def test_classify_scrape_log_status_known_sets():
    assert classify_scrape_log_status("success") == BUCKET_SUCCESSFUL
    assert classify_scrape_log_status("no_change") == BUCKET_UNCHANGED
    assert classify_scrape_log_status("not_a_product") == BUCKET_FILTERED
    assert classify_scrape_log_status("technical_error") == BUCKET_FAILED
    assert classify_scrape_log_status("persist_failed") == BUCKET_FAILED


def test_classify_scrape_log_status_unknown_returns_none():
    assert classify_scrape_log_status("mystery_status") is None


def test_aggregate_marketplace_log_rows_honest_four_buckets():
    mp_id = uuid4()
    rows = [
        SimpleNamespace(marketplace_id=mp_id, status="success", count=3),
        SimpleNamespace(marketplace_id=mp_id, status="no_change", count=2),
        SimpleNamespace(marketplace_id=mp_id, status="not_a_product", count=5),
        SimpleNamespace(marketplace_id=mp_id, status="error", count=1),
        SimpleNamespace(marketplace_id=mp_id, status="timeout", count=2),
    ]
    out = aggregate_marketplace_log_rows(rows)
    buckets = out[mp_id]
    assert buckets[BUCKET_SUCCESSFUL] == 3
    assert buckets[BUCKET_UNCHANGED] == 2
    assert buckets[BUCKET_FILTERED] == 5
    assert buckets[BUCKET_FAILED] == 3
    assert buckets["total"] == 13


def test_aggregate_marketplace_log_rows_excludes_unknown_status():
    mp_id = uuid4()
    rows = [
        SimpleNamespace(marketplace_id=mp_id, status="success", count=1),
        SimpleNamespace(marketplace_id=mp_id, status="brand_new_status", count=9),
    ]
    out = aggregate_marketplace_log_rows(rows)
    buckets = out[mp_id]
    assert buckets[BUCKET_SUCCESSFUL] == 1
    assert buckets["total"] == 1


def test_sum_buckets_across_marketplaces():
    mp_a, mp_b = uuid4(), uuid4()
    by_mp = {
        mp_a: {
            BUCKET_SUCCESSFUL: 2,
            BUCKET_UNCHANGED: 1,
            BUCKET_FILTERED: 0,
            BUCKET_FAILED: 1,
            "total": 4,
        },
        mp_b: {
            BUCKET_SUCCESSFUL: 1,
            BUCKET_UNCHANGED: 0,
            BUCKET_FILTERED: 3,
            BUCKET_FAILED: 0,
            "total": 4,
        },
    }
    totals = sum_buckets_across_marketplaces(by_mp)
    assert totals[BUCKET_SUCCESSFUL] == 3
    assert totals[BUCKET_UNCHANGED] == 1
    assert totals[BUCKET_FILTERED] == 3
    assert totals[BUCKET_FAILED] == 1
    assert totals["total"] == 8
    assert empty_outcome_buckets()["total"] == 0


# Co-update with alembic 024_reject_data_and_not_a_product (_STATUSES_WITH_NOT_A_PRODUCT).
_MIGRATION_024_SCRAPE_LOG_STATUSES = frozenset(
    {
        "success",
        "no_change",
        "error",
        "timeout",
        "blocked",
        "captcha",
        "not_found",
        "price_not_found",
        "parse_error",
        "currency_rejected",
        "not_a_product",
        "missing_critical_data",
        "technical_error",
        "fetch_failed",
        "parse_failed",
        "quota_exceeded",
        "persist_failed",
    }
)


def test_canonical_scrape_log_statuses_matches_bucket_union():
    bucket_union = (
        TERMINAL_SUCCESSFUL | TERMINAL_UNCHANGED | TERMINAL_FILTERED | TERMINAL_FAILED
    )
    assert frozenset(CANONICAL_SCRAPE_LOG_STATUSES) == bucket_union
    assert frozenset(CANONICAL_SCRAPE_LOG_STATUSES) == ALL_KNOWN_TERMINAL_STATUSES
    assert CANONICAL_SCRAPE_LOG_STATUSES == tuple(sorted(bucket_union))
    assert len(CANONICAL_SCRAPE_LOG_STATUSES) == 17


def test_canonical_scrape_log_statuses_matches_migration_024_check():
    assert frozenset(CANONICAL_SCRAPE_LOG_STATUSES) == _MIGRATION_024_SCRAPE_LOG_STATUSES


def test_repair_sites_import_canonical_status_tuple():
    from app.modules.scraper import service as scraper_service
    from app.modules.scraper import tasks as scraper_tasks

    assert "_SCRAPE_LOG_STATUSES" not in scraper_tasks.__dict__
    assert "_SCRAPE_LOG_STATUSES" not in scraper_service.__dict__
    assert scraper_tasks.CANONICAL_SCRAPE_LOG_STATUSES is CANONICAL_SCRAPE_LOG_STATUSES
    assert scraper_service.CANONICAL_SCRAPE_LOG_STATUSES is CANONICAL_SCRAPE_LOG_STATUSES
