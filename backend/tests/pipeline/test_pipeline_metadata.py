"""Tests for pipeline metadata helpers on Celery tasks."""

from __future__ import annotations

from app.modules.scraper.tasks import _extract_pipeline_metadata


def test_extract_pipeline_metadata_handles_invalid_shapes():
    """Metadata extractor always returns compatible defaults for malformed config."""
    default_meta = _extract_pipeline_metadata(None)
    assert default_meta["current_stage"] == "queued"
    assert "timings" in default_meta
    assert "summary" in default_meta
    assert "per_marketplace" in default_meta

    from_nested = _extract_pipeline_metadata({"metadata": {"current_stage": "scrape"}})
    assert from_nested["current_stage"] == "scrape"
