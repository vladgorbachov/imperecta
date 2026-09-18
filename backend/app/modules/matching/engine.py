"""Matching engine — incremental brand+model grouping over dim_product.

Slice M1 (docs/MATCHING_PLAN.md): every tick drains a batch of products
whose match_method is still NULL (partial pending index, migration 061),
extracts match signatures, and gate-writes either a deterministic
match_group_id ('brand_model') or the 'unmatched' marker so a row is
never rescanned. All writes go through the dim_product.product_match
door, pipelined via exec_write_records with a per-record fallback.
"""

from __future__ import annotations

from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError

from app.models.dimensions import DimBrand, DimProduct
from app.modules.data_firewall.update_validator import authorize_scrape_update
import uuid

from app.modules.matching.signature import (
    MATCH_NAMESPACE,
    extract_signature,
    match_group_id,
)
from app.modules.persist.gate_rpc import (
    GateRpcError,
    exec_write_record,
    exec_write_records,
)

slog = structlog.get_logger(__name__)

MATCH_BATCH_SIZE = 10_000
WRITE_CHUNK_SIZE = 100
GTIN_SWEEP_ROWS = 1_000
TITLE_SWEEP_ROWS = 1_000
METHOD_GTIN = "gtin"
METHOD_BRAND_MODEL = "brand_model"
METHOD_TITLE_EXACT = "title_exact"
METHOD_UNMATCHED = "unmatched"
CONFIDENCE_GTIN = 0.99
CONFIDENCE_TITLE_EXACT = 0.85
REJECT_SOURCE = "product_match"


def fetch_known_brands_sync() -> frozenset[str]:
    """Known-brand tokens from dim_brand (raises signature confidence)."""
    from app.database import sync_session_factory

    db = sync_session_factory()
    try:
        rows = db.execute(
            select(DimBrand.name_normalized).where(DimBrand.is_active)
        ).scalars()
        return frozenset(name.strip().lower() for name in rows if name)
    finally:
        db.close()


def fetch_pending_products_sync(
    limit: int,
) -> list[tuple[str, str | None, str | None, str | None, str | None]]:
    """(id, name_normalized, sku_universal, title_en, product_type_en) batch
    of not-yet-processed active products."""
    from app.database import sync_session_factory

    db = sync_session_factory()
    try:
        rows = db.execute(
            select(
                DimProduct.id,
                DimProduct.name_normalized,
                DimProduct.sku_universal,
                DimProduct.title_en,
                DimProduct.product_type_en,
            )
            .where(DimProduct.is_active, DimProduct.match_method.is_(None))
            .order_by(DimProduct.id)
            .limit(limit)
        ).all()
        return [
            (str(pid), name, sku, title_en, type_en)
            for pid, name, sku, title_en, type_en in rows
        ]
    finally:
        db.close()


def fetch_gtin_sweep_sync(limit: int) -> list[tuple[str, str]]:
    """(id, sku_universal) of products whose gtin arrived after matching.

    A gtin group id always beats a brand_model/title/unmatched verdict —
    the sweep upgrades them incrementally (index 063)."""
    from app.database import sync_session_factory

    db = sync_session_factory()
    try:
        rows = db.execute(
            select(DimProduct.id, DimProduct.sku_universal)
            .where(
                DimProduct.is_active,
                DimProduct.sku_universal.isnot(None),
                DimProduct.match_method.is_distinct_from(METHOD_GTIN),
            )
            .order_by(DimProduct.id)
            .limit(limit)
        ).all()
        return [(str(pid), sku) for pid, sku in rows]
    finally:
        db.close()


def fetch_title_sweep_sync(limit: int) -> list[tuple[str, str, str | None]]:
    """(id, title_en, product_type_en) of 'unmatched' rows whose EN title
    arrived after matching (enrichment fills it later; index 063)."""
    from app.database import sync_session_factory

    db = sync_session_factory()
    try:
        rows = db.execute(
            select(
                DimProduct.id,
                DimProduct.title_en,
                DimProduct.product_type_en,
            )
            .where(
                DimProduct.is_active,
                DimProduct.match_method == METHOD_UNMATCHED,
                DimProduct.title_en.isnot(None),
            )
            .order_by(DimProduct.id)
            .limit(limit)
        ).all()
        return [(str(pid), title, type_en) for pid, title, type_en in rows]
    finally:
        db.close()


def _normalize_title_key(title_en: str) -> str:
    """Deterministic key text for title_exact groups."""
    return " ".join(title_en.lower().split())[:500]


def gtin_group_id(gtin: str) -> uuid.UUID:
    """Deterministic group id for a GTIN ("gtin:" prefix — ':' cannot occur
    in brand_model "brand|code" keys, so the id spaces are disjoint)."""
    return uuid.uuid5(MATCH_NAMESPACE, f"gtin:{gtin.strip()}")


def title_group_id(title_en: str, product_type_en: str | None) -> uuid.UUID:
    """Deterministic group id for an exact normalized EN title within a type."""
    type_key = (product_type_en or "").strip().lower()
    return uuid.uuid5(
        MATCH_NAMESPACE, f"title:{type_key}:{_normalize_title_key(title_en)}"
    )


def build_gtin_fields(product_id: str, gtin: str) -> dict[str, Any]:
    return {
        "id": product_id,
        "match_group_id": str(gtin_group_id(gtin)),
        "match_method": METHOD_GTIN,
        "match_confidence": CONFIDENCE_GTIN,
    }


def build_title_fields(
    product_id: str, title_en: str, product_type_en: str | None
) -> dict[str, Any]:
    return {
        "id": product_id,
        "match_group_id": str(title_group_id(title_en, product_type_en)),
        "match_method": METHOD_TITLE_EXACT,
        "match_confidence": CONFIDENCE_TITLE_EXACT,
    }


def build_match_fields(
    product_id: str,
    signature: dict | None,
    *,
    sku_universal: str | None = None,
    title_en: str | None = None,
    product_type_en: str | None = None,
) -> dict[str, Any]:
    """Gate-payload for one product, best method first.

    Priority: gtin (global identity) > brand_model (signature) >
    title_exact (identical normalized EN title within a type) > unmatched.
    """
    if sku_universal and sku_universal.strip():
        return build_gtin_fields(product_id, sku_universal)
    if signature is not None:
        group = match_group_id(signature["brand"], signature["code"])
        return {
            "id": product_id,
            "match_group_id": str(group),
            "match_method": METHOD_BRAND_MODEL,
            "match_confidence": signature["confidence"],
        }
    if title_en and title_en.strip():
        return build_title_fields(product_id, title_en, product_type_en)
    return {"id": product_id, "match_method": METHOD_UNMATCHED}


def _sign_records(payloads: list[dict[str, Any]]) -> list:
    signed = []
    for fields in payloads:
        outcome = authorize_scrape_update(
            table="dim_product",
            kind="product_match",
            fields=fields,
            reject_source=REJECT_SOURCE,
        )
        if outcome.passed and outcome.signed_record is not None:
            signed.append(outcome.signed_record)
    return signed


def write_match_results_sync(payloads: list[dict[str, Any]]) -> int:
    """Pipelined gated updates; chunk failure degrades to per-record writes."""
    from app.database import sync_session_factory

    signed = _sign_records(payloads)
    if not signed:
        return 0
    written = 0
    db = sync_session_factory()
    try:
        for start in range(0, len(signed), WRITE_CHUNK_SIZE):
            chunk = signed[start : start + WRITE_CHUNK_SIZE]
            try:
                written += exec_write_records(db, chunk)
                db.commit()
            except (GateRpcError, DBAPIError):
                db.rollback()
                for record in chunk:
                    try:
                        written += exec_write_record(db, record)
                        db.commit()
                    except (GateRpcError, DBAPIError):
                        db.rollback()
        return written
    finally:
        db.close()


def run_match_tick(batch_size: int = MATCH_BATCH_SIZE) -> dict[str, int]:
    """One incremental matching pass; returns counters for the beat log.

    Three phases per tick: the pending drain (method priority gtin >
    brand_model > title_exact > unmatched), then two small upgrade sweeps
    for identity data that arrived AFTER a product was matched (gtin from
    PDP scrapes, title_en from enrichment).
    """
    known_brands = fetch_known_brands_sync()
    pending = fetch_pending_products_sync(batch_size)

    payloads: list[dict[str, Any]] = []
    matched = 0
    for product_id, name, sku, title_en, type_en in pending:
        signature = extract_signature(name, known_brands)
        fields = build_match_fields(
            product_id,
            signature,
            sku_universal=sku,
            title_en=title_en,
            product_type_en=type_en,
        )
        if fields["match_method"] != METHOD_UNMATCHED:
            matched += 1
        payloads.append(fields)

    gtin_swept = fetch_gtin_sweep_sync(GTIN_SWEEP_ROWS)
    for product_id, sku in gtin_swept:
        payloads.append(build_gtin_fields(product_id, sku))

    title_swept = fetch_title_sweep_sync(TITLE_SWEEP_ROWS)
    for product_id, title_en, type_en in title_swept:
        payloads.append(build_title_fields(product_id, title_en, type_en))

    written = write_match_results_sync(payloads)
    summary = {
        "scanned": len(pending),
        "matched": matched,
        "unmatched": len(pending) - matched,
        "gtin_swept": len(gtin_swept),
        "title_swept": len(title_swept),
        "written": written,
    }
    slog.info("product_match_tick_done", **summary)
    return summary
