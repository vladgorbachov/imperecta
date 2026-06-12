"""Full pipeline orchestration (discovery → scrape → persist)."""

from app.modules.scraper.pipeline.metadata_store import PipelineMetadataStore

__all__ = ["PipelineMetadataStore"]
