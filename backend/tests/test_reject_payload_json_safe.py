"""Reject payloads must survive stdlib-json serialization (PYTHON-FASTAPI-Q)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from app.modules.data_firewall.reject_store import _json_safe, _reject_data_row


def test_json_safe_converts_uuid_datetime_decimal():
    payload = {
        "listing_id": uuid4(),
        "scraped_at": datetime(2026, 9, 15, 4, 48, tzinfo=UTC),
        "price": Decimal("19.99"),
        "nested": {"marketplace_id": uuid4(), "tags": [uuid4(), "ok", 3]},
        "flag": True,
        "none": None,
    }
    safe = _json_safe(payload)
    json.dumps(safe)  # must not raise
    assert safe["flag"] is True and safe["none"] is None
    assert isinstance(safe["listing_id"], str)
    assert isinstance(safe["nested"]["marketplace_id"], str)


def test_reject_row_payload_is_json_serializable():
    row = _reject_data_row(
        source="ecommerce_scrape",
        table_target="fact_price",
        reject_reason="currency_country_mismatch",
        raw_payload={"listing_id": uuid4(), "marketplace_id": uuid4()},
        rejected_by="data_firewall",
    )
    json.dumps(row.raw_payload)  # must not raise
