"""data_firewall stage 1.2 — HMAC boundary, persist_module, active rules."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.modules.data_firewall.firewall import (
    FORCED_NOT_A_PRODUCT,
    REJECT_CONTRACT_VIOLATION,
    REJECT_NOT_A_PRODUCT_PAGE,
    evaluate_ecommerce,
    evaluate_market,
)
from app.modules.data_firewall.reject_store import reset_reject_spike_state
from app.modules.data_firewall.signing import (
    SignedRecord,
    canonical_serialize,
    reset_signing_settings_cache,
    sign,
    verify,
)
from app.modules.persist.writer import PersistContext, build_fact_price_fields, write_sync
from app.models.facts import FactPrice


class _FakeResolver:
    def matches(self, _marketplace_id, currency: str | None) -> bool:  # noqa: ANN001
        return bool(currency and currency.upper() in {"EUR", "USD", "EURO"})


@dataclass
class _FakeData:
    product_name: str | None = "Widget"
    title: str | None = "Widget"
    price: float | None = 19.0
    currency: str | None = "EUR"
    currency_raw: str | None = "19.0 EUR"
    page_role: str | None = "product"


@pytest.fixture(autouse=True)
def _data_firewall_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATA_FIREWALL_SIGNING_SECRET", "unit-test-data-firewall-secret")
    reset_signing_settings_cache()
    reset_reject_spike_state()
    yield
    reset_signing_settings_cache()
    reset_reject_spike_state()


def test_data_firewall_signature_unforgeable() -> None:
    fields = {"price": 12.34, "currency_code": "EUR"}
    signature = sign(fields)
    assert signature is not None
    assert verify(fields, signature) is True
    tampered = dict(fields)
    tampered["price"] = 99.99
    assert verify(tampered, signature) is False
    assert verify(fields, "deadbeef" * 8) is False


def test_data_firewall_signature_content_binding_bytes() -> None:
    a = canonical_serialize({"b": 1, "a": 2})
    b = canonical_serialize({"a": 2, "b": 1})
    assert a == b


def test_persist_rejects_unsigned() -> None:
    db = MagicMock()
    fields = {"price": 1.0, "currency_code": "EUR"}
    signed = SignedRecord(table="fact_price", fields=fields, signature="invalid")
    wrote = write_sync(
        db,
        signed,
        ctx=PersistContext(source="ecommerce_scrape"),
    )
    assert wrote is False
    added = [c.args[0] for c in db.add.call_args_list]
    assert not any(isinstance(a, FactPrice) for a in added)


def test_persist_writes_verbatim_no_mutation() -> None:
    db = MagicMock()
    listing_id = uuid4()
    now = datetime.now(tz=timezone.utc)
    fields = build_fact_price_fields(
        listing_id=listing_id,
        date_id=20990101,
        price=12.34,
        currency_code="EUR",
        original_price=None,
        discount_pct=None,
        price_change_pct=None,
        scraped_at=now,
        scrape_job_id=None,
    )
    signature = sign(fields)
    assert signature is not None
    signed = SignedRecord(table="fact_price", fields=fields, signature=signature)
    wrote = write_sync(
        db,
        signed,
        ctx=PersistContext(source="ecommerce_scrape", listing_id=listing_id),
    )
    assert wrote is True
    fact_rows = [c.args[0] for c in db.add.call_args_list if isinstance(c.args[0], FactPrice)]
    assert len(fact_rows) == 1
    row = fact_rows[0]
    assert float(row.price) == 12.34
    assert row.currency_code == "EUR"


def test_data_firewall_rejects_long_currency_no_truncate() -> None:
    mp_id = uuid4()
    listing_id = uuid4()
    data = _FakeData(currency="EURO")
    now = datetime.now(tz=timezone.utc)
    fields = build_fact_price_fields(
        listing_id=listing_id,
        date_id=20990101,
        price=10.0,
        currency_code="EURO",
        original_price=None,
        discount_pct=None,
        price_change_pct=None,
        scraped_at=now,
        scrape_job_id=None,
    )
    db = MagicMock()
    outcome = evaluate_ecommerce(
        data,
        marketplace_id=mp_id,
        currency_resolver=_FakeResolver(),
        page_role="product",
        persist_fields=fields,
        db=db,
        listing_id=listing_id,
    )
    assert not outcome.passed
    assert outcome.reject_reason == REJECT_CONTRACT_VIOLATION
    assert any("length:currency_code" in r for r in outcome.failed_rules)


@pytest.mark.parametrize("role", ["listing", "hub"])
def test_data_firewall_category_page_blocked(role: str) -> None:
    mp_id = uuid4()
    data = _FakeData(page_role=role)
    outcome = evaluate_ecommerce(
        data,
        marketplace_id=mp_id,
        currency_resolver=_FakeResolver(),
        page_role=role,
    )
    assert not outcome.passed
    assert outcome.reject_reason == FORCED_NOT_A_PRODUCT
    assert outcome.forced_log_status == FORCED_NOT_A_PRODUCT


def test_data_firewall_category_unknown_passes() -> None:
    mp_id = uuid4()
    listing_id = uuid4()
    data = _FakeData(page_role="unknown")
    now = datetime.now(tz=timezone.utc)
    fields = build_fact_price_fields(
        listing_id=listing_id,
        date_id=20990101,
        price=10.0,
        currency_code="EUR",
        original_price=None,
        discount_pct=None,
        price_change_pct=None,
        scraped_at=now,
        scrape_job_id=None,
    )
    outcome = evaluate_ecommerce(
        data,
        marketplace_id=mp_id,
        currency_resolver=_FakeResolver(),
        page_role="unknown",
        persist_fields=fields,
    )
    assert outcome.passed
    assert outcome.signed_record is not None


def test_data_firewall_ignores_unknown_in_stock_key_in_persist_fields() -> None:
    """Extra keys not in the fact_price contract are ignored (not rejected)."""
    mp_id = uuid4()
    listing_id = uuid4()
    data = _FakeData()
    now = datetime.now(tz=timezone.utc)
    fields = build_fact_price_fields(
        listing_id=listing_id,
        date_id=20990101,
        price=10.0,
        currency_code="EUR",
        original_price=None,
        discount_pct=None,
        price_change_pct=None,
        scraped_at=now,
        scrape_job_id=None,
    )
    fields["in_stock"] = True
    outcome = evaluate_ecommerce(
        data,
        marketplace_id=mp_id,
        currency_resolver=_FakeResolver(),
        persist_fields=fields,
    )
    assert outcome.passed
    assert outcome.signed_record is not None
    from app.modules.data_firewall.contracts import FACT_TABLE_CONTRACTS

    assert "in_stock" not in FACT_TABLE_CONTRACTS["fact_price"]


def test_data_firewall_fail_closed_without_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATA_FIREWALL_SIGNING_SECRET", raising=False)
    reset_signing_settings_cache()
    mp_id = uuid4()
    listing_id = uuid4()
    data = _FakeData()
    now = datetime.now(tz=timezone.utc)
    fields = build_fact_price_fields(
        listing_id=listing_id,
        date_id=20990101,
        price=10.0,
        currency_code="EUR",
        original_price=None,
        discount_pct=None,
        price_change_pct=None,
        scraped_at=now,
        scrape_job_id=None,
    )
    outcome = evaluate_ecommerce(
        data,
        marketplace_id=mp_id,
        currency_resolver=_FakeResolver(),
        persist_fields=fields,
    )
    assert not outcome.passed
    assert outcome.signed_record is None
    db = MagicMock()
    wrote = write_sync(db, outcome.signed_record, ctx=PersistContext(source="ecommerce_scrape"))
    assert wrote is False


def test_market_data_firewall_wired_bad_source() -> None:
    fields = {
        "date_id": 20990101,
        "currency_code": "USD",
        "rate_to_eur": 0.9,
        "rate_to_usd": 1.0,
        "source": "not_a_real_source",
        "fetched_at": datetime.now(tz=timezone.utc).isoformat(),
    }
    outcome = evaluate_market(fields, table="fact_currency_rate")
    assert not outcome.passed
    assert outcome.reject_reason == REJECT_CONTRACT_VIOLATION


def test_market_data_firewall_wired_valid_source() -> None:
    fields = {
        "date_id": 20990101,
        "currency_code": "USD",
        "rate_to_eur": 0.9,
        "rate_to_usd": 1.0,
        "source": "custom",
        "fetched_at": datetime.now(tz=timezone.utc),
    }
    outcome = evaluate_market(fields, table="fact_currency_rate")
    assert outcome.passed
    assert outcome.signed_record is not None
    assert verify(outcome.signed_record.fields, outcome.signed_record.signature)


def test_reject_data_resilient() -> None:
    db = MagicMock()
    db.add.side_effect = RuntimeError("db down")
    with patch("app.modules.data_firewall.reject_store.logger") as mock_logger:
        from app.modules.data_firewall.reject_store import write_reject_data

        write_reject_data(
            db,
            source="ecommerce_scrape",
            table_target="fact_price",
            reject_reason="contract_violation",
            raw_payload={"currency_code": "EURO"},
            rejected_by="data_firewall",
        )
        mock_logger.exception.assert_called_once()


def test_market_data_ingestion_imports_data_firewall() -> None:
    from app.modules.market_data import ingestion as market_ingestion

    source = open(market_ingestion.__file__, encoding="utf-8").read()
    assert "evaluate_market" in source
    assert "write_async" in source
