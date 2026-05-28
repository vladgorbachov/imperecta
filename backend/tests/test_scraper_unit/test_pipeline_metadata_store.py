"""Unit tests for pipeline metadata JSONB persistence."""

from __future__ import annotations

from copy import deepcopy
from uuid import uuid4

import pytest
from sqlalchemy.orm.attributes import flag_modified

from app.models.app_tables import ScrapeJob
from app.modules.admin.parsing_admin import ParsingAdminService
from app.modules.scraper.pipeline.metadata_store import PipelineMetadataStore


def test_metadata_store_uses_deepcopy_and_flag_modified_pattern():
    """Config assignment must replace JSONB root to trigger ORM change tracking."""
    job = ScrapeJob(
        job_type="full_pipeline_test",
        status="running",
        config={"metadata": ParsingAdminService._build_initial_metadata()},
    )
    metadata = PipelineMetadataStore.extract(job.config)
    metadata["celery_task_id"] = "task-abc"
    metadata["current_stage"] = "discovery"
    job.config = {"metadata": deepcopy(metadata)}
    flag_modified(job, "config")
    stored = PipelineMetadataStore.extract(job.config)
    assert stored["celery_task_id"] == "task-abc"
    assert stored["current_stage"] == "discovery"
