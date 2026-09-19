"""uuid7 ids + set-based gate inserts (harvest optimisation: enumeration write path)."""

from __future__ import annotations

import time
from uuid import UUID

from app.common.uuid7 import uuid7


def test_uuid7_is_version_7_and_time_ordered():
    ids = [uuid7() for _ in range(500)]
    assert all(isinstance(u, UUID) and u.version == 7 for u in ids)
    assert all(u.variant == "specified in RFC 4122" for u in ids)
    # sorted by generation order (within one ms the random tail may reorder
    # a handful of ids, but the sequence is monotone across milliseconds)
    a = uuid7()
    time.sleep(0.002)
    b = uuid7()
    assert a < b
    ms_a = a.int >> 80
    assert abs(ms_a - time.time_ns() // 1_000_000) < 5_000


def test_build_fact_listing_fields_takes_optional_id():
    from uuid import uuid4

    from app.modules.persist.writer import build_fact_listing_fields

    base = dict(product_id=uuid4(), marketplace_id=uuid4(), external_url="https://s/p", url_hash="h")
    without = build_fact_listing_fields(**base)
    assert "id" not in without and list(without)[0] == "product_id"
    lid = uuid7()
    with_id = build_fact_listing_fields(listing_id=lid, **base)
    assert with_id["id"] == lid and list(with_id)[0] == "id"


def test_exec_write_rows_sends_one_statement_with_per_record_signatures():
    from unittest.mock import MagicMock

    from app.modules.data_firewall.signing import SignedRecord
    from app.modules.persist.gate_rpc import exec_write_rows

    db = MagicMock()
    db.execute.return_value.scalar_one.return_value = 2
    recs = [
        SignedRecord(table="dim_product", operation="insert", locator={}, fields={"id": "a", "name": "x"}, signature="s1"),
        SignedRecord(table="dim_product", operation="insert", locator={}, fields={"id": "b", "name": "y"}, signature="s2"),
    ]
    assert exec_write_rows(db, "dim_product", recs) == 2
    sql, params = db.execute.call_args.args
    assert "gate.exec_write_rows(:table" in str(sql) and str(sql).count(")::gate.row_payload") == 2
    assert params["sig0"] == "s1" and params["sig1"] == "s2" and params["table"] == "dim_product"
    assert exec_write_rows(db, "dim_product", []) == 0
