"""ING1 invariants: ingestion extracted as a Tier-1 module from the parser.

Covers:
  * gate-parity (5 checks + skip_reason mapping) including the klick.ee
    currency-raw glued-text case still rejected (proof gate untouched).
  * no_change path (skip_price_record true) -> no FactPrice row.
  * fact-write path (FactPrice constructed correctly + listing denorm).
  * dim_product enrichment rules (placeholder name replaced; image only when
    absent).
  * IngestionResult contract for pass/skip branches.
  * Transaction split: ingestion commits its work; ScrapeLog stays a
    separate parser commit; mid-stream commit failure surfaces as
    persist_failed without writing ScrapeLog.
  * Parser delegates to IngestionService (no inline FactPrice or gate left).
  * One-directional edge: ingestion does NOT import scraper / pool /
    extractor modules.
"""

from __future__ import annotations

import importlib
import inspect
import re
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.modules.ingestion.dto import IngestionResult
from app.modules.ingestion.gate import (
    MAX_CURRENCY_RAW_LEN,
    SKIP_CURRENCY_COUNTRY_MISMATCH,
    SKIP_CURRENCY_RAW_TOO_LONG,
    SKIP_MISSING_NAME_OR_CURRENCY,
    SKIP_PRICE_NOT_POSITIVE,
    CurrencyResolver,
    evaluate_gate,
)
from app.modules.ingestion.service import IngestionService


# ---------------------------------------------------------------------------
# Helpers — minimal in-memory fakes for the IngestionService unit tests
# ---------------------------------------------------------------------------


class _FakeResolver:
    """In-memory CurrencyResolver substitute (no DB calls)."""

    def __init__(self, allowed: set[str] | None = None) -> None:
        self._allowed = frozenset(c.upper() for c in (allowed or {"EUR", "USD"}))

    def whitelist_for(self, _marketplace_id):  # pragma: no cover - parity
        return self._allowed

    def matches(self, _marketplace_id, currency):
        if not self._allowed:
            return True
        if not currency:
            return False
        return currency.strip().upper() in self._allowed


def _make_data(**overrides):
    base = dict(
        product_name="Sample Title",
        title="Sample Title",
        price=99.99,
        currency="EUR",
        currency_raw="EUR",
        original_price=None,
        image_url="https://example.com/img.jpg",
        price_raw_text="99.99 EUR",
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def _make_listing(**overrides):
    base = dict(
        id=999,
        marketplace_id=1,
        product_id=42,
        external_url="https://example.com/product",
        last_price=None,
        last_currency_code=None,
        last_in_stock=None,
        last_price_changed_at=None,
        last_checked_at=None,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


# ---------------------------------------------------------------------------
# 1. Gate parity (5 checks + skip_reason taxonomy)
# ---------------------------------------------------------------------------


def test_gate_passes_for_valid_payload() -> None:
    outcome = evaluate_gate(
        _make_data(),
        marketplace_id=1,
        currency_resolver=_FakeResolver({"EUR", "USD"}),
    )
    assert outcome.passed
    assert outcome.skip_reason is None
    assert outcome.forced_log_status is None


def test_gate_rejects_currency_raw_glued_text_klick_ee_case() -> None:
    """klick.ee fix is a Phase 5 extractor concern; the gate STILL rejects.

    Proves the gate moved byte-for-byte and was not "improved" in ING1.
    """
    glued = "EUR " + "x" * MAX_CURRENCY_RAW_LEN
    assert len(glued) >= MAX_CURRENCY_RAW_LEN

    outcome = evaluate_gate(
        _make_data(currency_raw=glued),
        marketplace_id=1,
        currency_resolver=_FakeResolver({"EUR"}),
    )
    assert not outcome.passed
    assert not outcome.currency_raw_sane_ok
    assert outcome.skip_reason == SKIP_CURRENCY_RAW_TOO_LONG
    assert outcome.forced_log_status == "parse_error"


def test_gate_rejects_currency_country_mismatch() -> None:
    outcome = evaluate_gate(
        _make_data(currency="JPY"),
        marketplace_id=1,
        currency_resolver=_FakeResolver({"EUR"}),
    )
    assert not outcome.passed
    assert not outcome.currency_country_match_ok
    assert outcome.skip_reason == SKIP_CURRENCY_COUNTRY_MISMATCH
    assert outcome.forced_log_status == "parse_error"


def test_gate_rejects_missing_currency() -> None:
    outcome = evaluate_gate(
        _make_data(currency=None, currency_raw=""),
        marketplace_id=1,
        currency_resolver=_FakeResolver({"EUR"}),
    )
    assert not outcome.passed
    assert outcome.skip_reason == SKIP_MISSING_NAME_OR_CURRENCY
    assert outcome.forced_log_status is None


def test_gate_rejects_missing_product_name() -> None:
    outcome = evaluate_gate(
        _make_data(product_name=None, title=None),
        marketplace_id=1,
        currency_resolver=_FakeResolver({"EUR"}),
    )
    assert not outcome.passed
    assert outcome.skip_reason == SKIP_MISSING_NAME_OR_CURRENCY


def test_gate_rejects_non_positive_price() -> None:
    outcome = evaluate_gate(
        _make_data(price=0),
        marketplace_id=1,
        currency_resolver=_FakeResolver({"EUR"}),
    )
    assert not outcome.passed
    assert not outcome.price_ok
    assert outcome.skip_reason == SKIP_PRICE_NOT_POSITIVE


# ---------------------------------------------------------------------------
# 2. IngestionResult contract
# ---------------------------------------------------------------------------


def test_ingestion_result_is_frozen_dto() -> None:
    """IngestionResult is an immutable dataclass with the documented surface."""
    fields = IngestionResult.__dataclass_fields__
    assert set(fields.keys()) == {
        "persisted",
        "log_status",
        "skip_reason",
        "price_found",
        "in_stock_found",
        "persist_failed",
    }
    result = IngestionResult(
        persisted=True,
        log_status="success",
        price_found=1.0,
        in_stock_found=True,
    )
    with pytest.raises(Exception):
        result.persisted = False  # frozen


# ---------------------------------------------------------------------------
# 3. IngestionService.persist_extracted: success path + transaction
# ---------------------------------------------------------------------------


@pytest.fixture()
def patched_ingestion(monkeypatch):
    """Patch helpers so we never hit the DB during IngestionService unit tests."""
    monkeypatch.setattr(
        "app.modules.ingestion.service._today_date_id",
        lambda _db: 20990101,
    )
    monkeypatch.setattr(
        "app.modules.ingestion.service._previous_price_snapshot",
        lambda _db, _lid, _did: None,
    )
    yield


def test_persist_extracted_writes_fact_price_on_pass(patched_ingestion) -> None:
    db = MagicMock()
    db.get.return_value = SimpleNamespace(
        name="Sample Title",
        name_normalized="sample title",
        image_url="https://example.com/img.jpg",
    )
    listing = _make_listing()

    svc = IngestionService(db)
    svc._currency_resolver = _FakeResolver({"EUR"})

    result = svc.persist_extracted(
        data=_make_data(),
        listing=listing,
        extracted_in_stock=True,
    )

    added = [c.args[0] for c in db.add.call_args_list]
    fact_price_rows = [a for a in added if a.__class__.__name__ == "FactPrice"]
    assert len(fact_price_rows) == 1
    row = fact_price_rows[0]
    assert float(row.price) == 99.99
    assert row.currency_code == "EUR"
    assert row.in_stock is True

    assert listing.last_price == 99.99
    assert listing.last_currency_code == "EUR"
    assert listing.last_in_stock is True
    assert listing.last_price_changed_at is not None

    db.flush.assert_called()
    db.commit.assert_called_once()

    assert result.persisted is True
    assert result.log_status == "success"
    assert result.skip_reason is None
    assert result.price_found == 99.99
    assert result.in_stock_found is True
    assert result.persist_failed is False


def test_persist_extracted_no_change_path(patched_ingestion) -> None:
    """When _should_skip_price_record true: no FactPrice row, log_status no_change."""
    db = MagicMock()
    db.get.return_value = SimpleNamespace(
        name="Sample Title",
        name_normalized="sample title",
        image_url="https://example.com/img.jpg",
    )
    listing = _make_listing(
        last_price=99.99,
        last_currency_code="EUR",
        last_in_stock=True,
    )

    svc = IngestionService(db)
    svc._currency_resolver = _FakeResolver({"EUR"})

    result = svc.persist_extracted(
        data=_make_data(),
        listing=listing,
        extracted_in_stock=True,
    )

    added = [c.args[0] for c in db.add.call_args_list]
    fact_price_rows = [a for a in added if a.__class__.__name__ == "FactPrice"]
    assert fact_price_rows == []

    assert result.persisted is False
    assert result.log_status == "no_change"
    assert result.skip_reason is None
    db.commit.assert_called_once()


def test_persist_extracted_gate_skip_returns_parse_error(patched_ingestion) -> None:
    """Currency-raw too long -> persisted=False, log_status='parse_error'."""
    db = MagicMock()
    db.get.return_value = SimpleNamespace(name="X", name_normalized="x", image_url=None)
    listing = _make_listing()

    svc = IngestionService(db)
    svc._currency_resolver = _FakeResolver({"EUR"})

    glued = "EUR " + "x" * MAX_CURRENCY_RAW_LEN
    result = svc.persist_extracted(
        data=_make_data(currency_raw=glued),
        listing=listing,
        extracted_in_stock=None,
    )

    added = [c.args[0] for c in db.add.call_args_list]
    fact_price_rows = [a for a in added if a.__class__.__name__ == "FactPrice"]
    assert fact_price_rows == []

    assert result.persisted is False
    assert result.log_status == "parse_error"
    assert result.skip_reason == SKIP_CURRENCY_RAW_TOO_LONG


def test_persist_extracted_dim_enrichment_only_image_when_absent(
    patched_ingestion,
) -> None:
    db = MagicMock()
    existing_image = "https://example.com/old-image.jpg"
    product = SimpleNamespace(
        name="product",
        name_normalized="product",
        image_url=existing_image,
    )
    db.get.return_value = product
    listing = _make_listing()

    svc = IngestionService(db)
    svc._currency_resolver = _FakeResolver({"EUR"})

    svc.persist_extracted(
        data=_make_data(image_url="https://example.com/new-image.jpg"),
        listing=listing,
        extracted_in_stock=None,
    )

    assert product.image_url == existing_image
    assert product.name == "Sample Title"


# ---------------------------------------------------------------------------
# 4. Transaction split — ingestion commit | ScrapeLog commit (separate)
# ---------------------------------------------------------------------------


def test_persist_extracted_commit_failure_returns_persist_failed(
    patched_ingestion,
) -> None:
    db = MagicMock()
    db.get.return_value = SimpleNamespace(
        name="Sample Title",
        name_normalized="sample title",
        image_url=None,
    )
    db.commit.side_effect = RuntimeError("boom")
    listing = _make_listing()

    svc = IngestionService(db)
    svc._currency_resolver = _FakeResolver({"EUR"})

    result = svc.persist_extracted(
        data=_make_data(),
        listing=listing,
        extracted_in_stock=True,
    )

    assert result.persist_failed is True
    assert result.persisted is False
    db.rollback.assert_called_once()


def test_scrape_log_persist_is_separate_commit() -> None:
    """The parser commits the scrape_logs row in its OWN call, independent of
    ingestion. We confirm by reading the source of _persist_scrape_log: it
    must call db.commit() inside, not via IngestionService."""
    from app.modules.scraper import service as parser_svc

    src = inspect.getsource(parser_svc.GlobalScrapeService._persist_scrape_log)
    assert "self.db.commit()" in src
    # ScrapeLog persistence must not flow through IngestionService.
    assert "IngestionService" not in src


# ---------------------------------------------------------------------------
# 5. Parser delegates to IngestionService; inline gate / FactPrice removed
# ---------------------------------------------------------------------------


def test_parser_scrape_product_delegates_to_ingestion_service() -> None:
    from app.modules.scraper import service as parser_svc

    src = inspect.getsource(parser_svc.GlobalScrapeService.scrape_product)
    assert "IngestionService(self.db).persist_extracted(" in src
    # The parser no longer constructs FactPrice rows or runs the inline gate.
    assert "FactPrice(" not in src
    assert "PERSISTENCE_GATE" not in src


def test_scraper_service_no_longer_constructs_fact_price() -> None:
    """rg 'FactPrice(' must come up clean across the parser module."""
    parser_src = Path(
        importlib.import_module("app.modules.scraper.service").__file__
    ).read_text(encoding="utf-8")
    assert "FactPrice(" not in parser_src, (
        "FactPrice construction must live in the ingestion module only"
    )


# ---------------------------------------------------------------------------
# 6. One-directional edge: ingestion imports no scraper / pool / extractor code
# ---------------------------------------------------------------------------


_FORBIDDEN_IMPORT_PATTERN = re.compile(
    r"^\s*(?:from|import)\s+(?:app\.modules\.scraper|\.{1,2}scraper)\b"
)


def test_ingestion_does_not_import_parser_or_pool_or_extractor() -> None:
    ingestion_dir = Path(
        importlib.import_module("app.modules.ingestion").__file__
    ).parent
    offenders: list[tuple[str, int, str]] = []
    for py_file in sorted(ingestion_dir.glob("*.py")):
        for i, line in enumerate(
            py_file.read_text(encoding="utf-8").splitlines(), 1
        ):
            if _FORBIDDEN_IMPORT_PATTERN.match(line):
                offenders.append((py_file.name, i, line))
    assert not offenders, (
        "ingestion/ may not import scraper / pool / extractor code: "
        + repr(offenders)
    )


# ---------------------------------------------------------------------------
# 7. ScrapeLog & failure-path commit boundary in parser
# ---------------------------------------------------------------------------


def test_parser_keeps_consecutive_error_deactivation_and_scrape_log() -> None:
    """Parser still owns the consecutive-error LISTING_DEACTIVATE_AFTER_ERRORS
    path + ScrapeLog write (these are parser concerns, not ingestion)."""
    from app.modules.scraper import service as parser_svc

    src = inspect.getsource(parser_svc.GlobalScrapeService.scrape_product)
    assert "LISTING_DEACTIVATE_AFTER_ERRORS" in src
    assert "_persist_scrape_log(" in src


def test_parser_delegates_via_ingestion_service_with_listing_and_data(
    patched_ingestion, monkeypatch
) -> None:
    """End-to-end shape: GlobalScrapeService.scrape_product passes data +
    listing + extracted_in_stock into IngestionService.persist_extracted."""
    from app.modules.scraper import service as parser_svc

    captured: dict = {}

    class _CapturedIngestion:
        def __init__(self, db):
            captured["db"] = db

        def persist_extracted(
            self, *, data, listing, extracted_in_stock, scrape_job_id=None
        ):
            captured["data"] = data
            captured["listing"] = listing
            captured["extracted_in_stock"] = extracted_in_stock
            captured["scrape_job_id"] = scrape_job_id
            return IngestionResult(
                persisted=True,
                log_status="success",
                price_found=getattr(data, "price", None),
                in_stock_found=extracted_in_stock,
            )

    monkeypatch.setattr(parser_svc, "IngestionService", _CapturedIngestion)

    listing = _make_listing(scraper_config=None)
    listing.consecutive_errors = 0
    listing.last_error = None
    listing.is_active = True
    listing.scraper_config = None

    db = MagicMock()
    db.get.side_effect = [
        listing,  # FactListing lookup
        SimpleNamespace(  # DimMarketplace lookup
            requires_js=False,
            scrape_tier=1,
            custom_title_selector=None,
            custom_price_selector=None,
        ),
    ]
    pool = MagicMock()
    pool_data = _make_data(in_stock=True)
    pool_result = SimpleNamespace(
        success=True,
        url=listing.external_url,
        data=pool_data,
        scraper_layer="httpx",
        duration_ms=12,
        error=None,
        is_partial=False,
        is_empty=False,
        missing_fields=[],
        in_stock=True,
        log_status=None,
    )
    with patch(
        "app.modules.scraper.service._run_coro_in_worker",
        return_value=pool_result,
    ):
        with patch.object(
            parser_svc.GlobalScrapeService,
            "_persist_scrape_log",
            return_value=True,
        ):
            parser_svc.GlobalScrapeService(db, pool).scrape_product(listing.id)

    assert captured["data"] is pool_data
    assert captured["listing"] is listing
    assert captured["extracted_in_stock"] is True
    assert captured["scrape_job_id"] is None
