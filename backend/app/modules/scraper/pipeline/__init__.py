"""Full pipeline orchestration (discovery → scrape → persist)."""

from app.modules.scraper.pipeline.metadata_store import PipelineMetadataStore

__all__ = ["FullPipelineTestRunner", "PipelineMetadataStore"]


def __getattr__(name: str):
    if name == "FullPipelineTestRunner":
        from app.modules.scraper.pipeline.full_test_runner import FullPipelineTestRunner

        return FullPipelineTestRunner
    raise AttributeError(name)
