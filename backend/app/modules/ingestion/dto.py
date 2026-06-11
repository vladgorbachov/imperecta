"""Immutable result DTO returned by IngestionService.persist_extracted."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class IngestionResult:
    """Outcome of a single ingestion attempt.

    Fields:
        persisted: True when a FactPrice row was written (success path).
            False for both gate-rejection and the ``no_change`` skip path.
        log_status: forced scrape_logs.status the parser should record.
            One of ``success`` | ``no_change`` | ``parse_error`` | ``None``
            (None lets the parser run its own classifier).
        skip_reason: why the gate rejected, when applicable.
            One of ``missing_name_or_currency`` | ``currency_raw_too_long``
            | ``currency_country_mismatch`` | None.
        price_found: the parsed price the parser logs into scrape_logs.
        in_stock_found: the resolved in-stock flag the parser logs.
        persist_failed: True when ingestion's own commit raised (rare).
            Parser uses this to short-circuit ScrapeLog and return
            persist_failed to its caller (today's behaviour).
    """

    persisted: bool
    log_status: str | None
    skip_reason: str | None = None
    price_found: float | None = None
    in_stock_found: bool | None = None
    persist_failed: bool = False
