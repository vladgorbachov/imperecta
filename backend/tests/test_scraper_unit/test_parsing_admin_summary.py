"""Admin summary field helper for honest scrape outcome buckets."""

from __future__ import annotations

from unittest.mock import MagicMock

from app.modules.admin.parsing_admin import ParsingAdminService


def test_summary_response_fields_adds_outcome_buckets():
    job = MagicMock()
    job.total_listings = 12
    job.successful = 8
    job.failed = 2
    summary = {
        "listings_created": 12,
        "prices_saved": 8,
        "errors_count": 3,
        "successful": 8,
        "unchanged": 4,
        "filtered": 6,
        "failed": 2,
        "total": 20,
    }
    out = ParsingAdminService._summary_response_fields(summary, job)
    assert out["listings_created"] == 12
    assert out["prices_saved"] == 8
    assert out["errors_count"] == 3
    assert out["successful"] == 8
    assert out["unchanged"] == 4
    assert out["filtered"] == 6
    assert out["failed"] == 2
    assert out["total"] == 20
