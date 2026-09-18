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
from app.modules.matching.signature import extract_signature, match_group_id
from app.modules.persist.gate_rpc import (
    GateRpcError,
    exec_write_record,
    exec_write_records,
)

slog = structlog.get_logger(__name__)

MATCH_BATCH_SIZE = 10_000
WRITE_CHUNK_SIZE = 100
METHOD_BRAND_MODEL = "brand_model"
METHOD_UNMATCHED = "unmatched"
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


def fetch_pending_products_sync(limit: int) -> list[tuple[str, str | None]]:
    """(id, name_normalized) batch of not-yet-processed active products."""
    from app.database import sync_session_factory

    db = sync_session_factory()
    try:
        rows = db.execute(
            select(DimProduct.id, DimProduct.name_normalized)
            .where(DimProduct.is_active, DimProduct.match_method.is_(None))
            .order_by(DimProduct.id)
            .limit(limit)
        ).all()
        return [(str(pid), name) for pid, name in rows]
    finally:
        db.close()


def build_match_fields(
    product_id: str,
    signature: dict | None,
) -> dict[str, Any]:
    """Gate-payload for one product: group assignment or unmatched marker."""
    if signature is None:
        return {"id": product_id, "match_method": METHOD_UNMATCHED}
    group = match_group_id(signature["brand"], signature["code"])
    return {
        "id": product_id,
        "match_group_id": str(group),
        "match_method": METHOD_BRAND_MODEL,
        "match_confidence": signature["confidence"],
    }


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
    """One incremental matching pass; returns counters for the beat log."""
    known_brands = fetch_known_brands_sync()
    pending = fetch_pending_products_sync(batch_size)
    if not pending:
        return {"scanned": 0, "matched": 0, "unmatched": 0, "written": 0}

    payloads: list[dict[str, Any]] = []
    matched = 0
    for product_id, name in pending:
        signature = extract_signature(name, known_brands)
        if signature is not None:
            matched += 1
        payloads.append(build_match_fields(product_id, signature))

    written = write_match_results_sync(payloads)
    summary = {
        "scanned": len(pending),
        "matched": matched,
        "unmatched": len(pending) - matched,
        "written": written,
    }
    slog.info("product_match_tick_done", **summary)
    return summary
