"""P12: keyset pagination + capped/estimated counts for /pool/products."""

from __future__ import annotations

from datetime import datetime, timezone

from app.main import app
from app.modules.product_pool import service as ps


def test_cursor_roundtrip_and_garbage_rejected():
    payload = {"d": "next", "v": "2026-09-18T00:00:00+00:00", "id": "abc"}
    token = ps._encode_cursor(payload)
    assert ps._decode_cursor(token) == payload
    assert ps._decode_cursor("!!!not-base64!!!") is None
    assert ps._decode_cursor(ps._encode_cursor({"no": "id"})) is None


def test_keyset_columns_cover_default_and_exclude_computed_sorts():
    assert ps._keyset_columns("recent") is not None
    assert ps._keyset_columns("name_asc") is not None
    assert ps._keyset_columns("price_desc") is not None
    for computed in ("gainers", "losers", "volatile"):
        assert ps._keyset_columns(computed) is None


def test_parse_cursor_value_types():
    dt = ps._parse_cursor_value("recent", "2026-09-18T10:00:00+00:00")
    assert isinstance(dt, datetime) and dt.tzinfo is not None
    assert ps._parse_cursor_value("price_asc", "12.5") == 12.5
    assert ps._parse_cursor_value("name_asc", "Widget") == "Widget"
    assert ps._parse_cursor_value("recent", None) is None


def test_keyset_where_shapes():
    col = ps.FactListing.last_checked_at
    now = datetime.now(tz=timezone.utc)
    # Forward after a non-null key: strictly-after rows OR the NULL tail.
    fwd = ps._keyset_where(col, "desc", now, "00000000-0000-0000-0000-000000000001", backwards=False)
    sql = str(fwd)
    assert "last_checked_at <" in sql and "IS NULL" in sql
    # Forward inside the NULL tail: only later NULL rows.
    fwd_null = ps._keyset_where(col, "desc", None, "00000000-0000-0000-0000-000000000001", backwards=False)
    sql_null = str(fwd_null)
    assert "IS NULL" in sql_null and "id >" in sql_null and "<" not in sql_null.replace("id >", "")
    # Backwards from the NULL tail reaches every non-null row.
    back_null = ps._keyset_where(col, "desc", None, "00000000-0000-0000-0000-000000000001", backwards=True)
    assert "IS NOT NULL" in str(back_null)


def test_products_endpoint_declares_cursor_param_and_meta_fields():
    schema = app.openapi()
    params = {
        p["name"]
        for p in schema["paths"]["/api/pool/products"]["get"].get("parameters", [])
    }
    assert "cursor" in params
    envelope = schema["components"]["schemas"]["PoolProductsResponse"]["properties"]
    for field in ("total_is_estimate", "next_cursor", "prev_cursor"):
        assert field in envelope


def test_count_cap_constant_sane():
    assert ps.COUNT_CAP == 10_000
