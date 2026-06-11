"""Ingestion Tier-1 module.

Owns the PERSISTENCE_GATE (5-check quality gate), FactPrice write +
price-change/discount, DimProduct name/image enrichment, and FactListing
denormalised price-field updates. Receives ``ExtractedProduct`` from the
scraper parser; will also be the persistence path for the Phase 4 user-upload
rail (multi-consumer entry point).

Public surface:
    - ``IngestionService`` (service.py): persist_extracted(...) -> IngestionResult
    - ``IngestionResult`` (dto.py): immutable result DTO
    - ``GateOutcome``, ``evaluate_gate`` (gate.py): pure-ish gate + helpers
"""
