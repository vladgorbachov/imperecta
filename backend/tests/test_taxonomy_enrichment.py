"""P13 enrichment: prompt/reply parsing, gate doors, honest-null discipline."""

from __future__ import annotations

import json

from app.modules.data_firewall.update_validator import SCRAPE_UPDATE_ALLOWLIST
from app.modules.enrichment import taxonomy as tx


def test_category_reply_parsing_tolerates_fences_and_garbage():
    names = {"0": "LAPTOPURI", "1": "CEASURI INTELIGENTE"}
    reply = '```json\n{"0": "Laptops", "1": "Smartwatches", "9": "Ghost"}\n```'
    parsed = tx.parse_category_reply(reply, names)
    assert parsed == {"0": "Laptops", "1": "Smartwatches"}
    assert tx.parse_category_reply("not json at all", names) == {}


def test_product_reply_requires_type_en_and_drops_unknown_indexes():
    titles = {"0": "Laptop Lenovo IdeaPad 5", "1": "Hõbedane 925 ripats"}
    reply = json.dumps(
        {
            "0": {"type": "laptop", "type_en": "laptop", "title_en": "Lenovo IdeaPad 5 Laptop"},
            "1": {"type": "ripats", "type_en": ""},
            "7": {"type_en": "ghost"},
        }
    )
    parsed = tx.parse_product_reply(reply, titles)
    assert set(parsed.keys()) == {"0"}
    # Type names are capitalized at write time (user rule for the Type column).
    assert parsed["0"]["product_type_en"] == "Laptop"
    assert parsed["0"]["product_type"] == "Laptop"
    assert parsed["0"]["title_en"] == "Lenovo IdeaPad 5 Laptop"


def test_type_capitalization_preserves_inner_casing():
    titles = {"0": "iPhone 15 case"}
    reply = json.dumps({"0": {"type": "чехол", "type_en": "iPhone case"}})
    parsed = tx.parse_product_reply(reply, titles)
    # First letter uppercased, inner casing untouched (no str.capitalize).
    assert parsed["0"]["product_type_en"] == "IPhone case"
    assert parsed["0"]["product_type"] == "Чехол"


def test_prompts_embed_payload_json():
    names = {"0": "Sülearvutid"}
    assert "Sülearvutid" in tx.build_category_prompt(names)
    assert "Sülearvutid" in tx.build_product_prompt(names)


def test_gate_doors_cover_enrichment_columns():
    assert SCRAPE_UPDATE_ALLOWLIST["dim_category"]["category_translate"] == frozenset(
        {"name_en"}
    )
    enrich = SCRAPE_UPDATE_ALLOWLIST["dim_product"]["product_enrich"]
    for col in ("product_type", "product_type_en", "title_en"):
        assert col in enrich


def test_reuse_pass_copies_donor_columns_through_gate():
    from unittest.mock import MagicMock, patch
    from uuid import uuid4

    target_id, twin_id = uuid4(), uuid4()
    donors = [
        ("lenovo ideapad 5", "sülearvuti", "laptop", "Lenovo IdeaPad 5 Laptop"),
        ("apple watch se", None, "smartwatch", None),
    ]
    targets = [
        (target_id, "lenovo ideapad 5"),
        (twin_id, "apple watch se"),
    ]
    db = MagicMock()
    donors_result = MagicMock()
    donors_result.all.return_value = donors
    targets_result = MagicMock()
    targets_result.all.return_value = targets
    db.execute.side_effect = [donors_result, targets_result]
    with patch("app.database.sync_session_factory", return_value=db), patch.object(
        tx, "write_product_types_sync", return_value=2
    ) as wp:
        written = tx.reuse_existing_enrichment_sync(500)
    assert written == 2
    updates = wp.call_args.args[0]
    assert updates[str(target_id)] == {
        "product_type_en": "laptop",
        "product_type": "sülearvuti",
        "title_en": "Lenovo IdeaPad 5 Laptop",
    }
    # Sparse donor: only the guaranteed column travels; nothing fabricated.
    assert updates[str(twin_id)] == {"product_type_en": "smartwatch"}


def test_reuse_pass_no_donors_short_circuits():
    from unittest.mock import MagicMock, patch

    db = MagicMock()
    empty = MagicMock()
    empty.all.return_value = []
    db.execute.return_value = empty
    with patch("app.database.sync_session_factory", return_value=db):
        assert tx.reuse_existing_enrichment_sync(500) == 0
    assert db.execute.call_count == 1  # never touches the untyped side


def test_beat_schedule_has_enrichment_tick():
    from app.workers.celery_app import celery_app  # noqa: PLC0415

    assert "taxonomy-enrich" in celery_app.conf.beat_schedule
    assert (
        celery_app.conf.beat_schedule["taxonomy-enrich"]["task"]
        == "taxonomy_enrich_tick"
    )


def test_proxy_usage_endpoint_registered():
    from app.main import app

    schema = app.openapi()
    assert "get" in schema["paths"].get("/api/admin/parsing/proxy-usage", {})


def test_usage_days_reader_shapes():
    from unittest.mock import MagicMock, patch

    from app.modules.scraper import proxy_provider_limiter as ppl

    client = MagicMock()
    client.mget.return_value = ["5", None, "12"]
    with patch.object(ppl, "_get_redis", return_value=client):
        out = ppl.read_usage_days_sync(3)
    assert len(out) == 3
    assert sorted(out.values()) == [0, 5, 12]


def test_fact_price_weekly_model_matches_retention_contract():
    from app.models.facts import FactPriceWeekly

    cols = {c.name for c in FactPriceWeekly.__table__.columns}
    assert {
        "listing_id",
        "week_start",
        "currency_code",
        "price_open",
        "price_close",
        "price_min",
        "price_max",
        "price_avg",
        "price_eur_close",
        "n_changes",
    } <= cols
    pk = {c.name for c in FactPriceWeekly.__table__.primary_key.columns}
    assert pk == {"listing_id", "week_start", "currency_code"}
