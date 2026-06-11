"""Classifier Tier-1 module.

Owns page-role classification via structural schema.org / OG / JSON-LD /
Microdata signals plus a Layer-3 structural fallback. Two consumers:
``app.modules.scraper.extractors.merge_and_finalize`` (extractor) and
``app.modules.scraper.discovery._classify_url`` (discovery).

Public surface:
    - ``PageRole`` (Literal["product","listing","hub","unknown"]) contract.
    - ``classify_page_role`` — structural Layer-3 fallback.
    - ``classify_page_role_for_discovery`` — full Layer-1/2/2.5/3 pipeline.
    - schema.org type-readers (``_get_og_type``, ``_get_jsonld_root_types``,
      ``_get_microdata_toplevel_types``) — used by classifier internally and
      reserved for the Phase 5 microdata-extraction strategy import surface.

Edge map (post-CLS1; no cycles):
    common.html_parsing  <-  classifier
    common.html_parsing  <-  extractor
    classifier           <-  extractor
    classifier           <-  discovery
    classifier imports nothing from extractor / scraper / discovery.
"""

from app.modules.classifier.service import (
    PageRole,
    classify_page_role,
    classify_page_role_for_discovery,
    _get_jsonld_root_types,
    _get_microdata_toplevel_types,
    _get_og_type,
)

__all__ = [
    "PageRole",
    "classify_page_role",
    "classify_page_role_for_discovery",
    "_get_og_type",
    "_get_jsonld_root_types",
    "_get_microdata_toplevel_types",
]
