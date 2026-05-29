"""Full pipeline orchestration (discovery → scrape → persist)."""

from app.modules.scraper.pipeline.metadata_store import PipelineMetadataStore

__all__ = ["FullPipelineOrchestrator", "PipelineMetadataStore"]


def __getattr__(name: str):
    if name == "FullPipelineOrchestrator":
        from app.modules.scraper.pipeline.orchestrator import FullPipelineOrchestrator

        return FullPipelineOrchestrator
    raise AttributeError(name)
