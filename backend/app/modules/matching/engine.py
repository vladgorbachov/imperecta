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
    score_titles,
    title_tokens,
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
METHOD_TITLE_SIM = "title_sim"
METHOD_UNMATCHED = "unmatched"
CONFIDENCE_GTIN = 0.99
CONFIDENCE_TITLE_EXACT = 0.85
CONFIDENCE_TITLE_SIM = 0.80
TITLE_SIM_THRESHOLD = 0.80
TITLE_MERGE_GROUPS_CAP = 2_000
TITLE_MERGE_WINDOW = 3
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
    """Deterministic key text for title_exact groups (M2b: normalized token
    set — stopwords dropped, units glued, sorted — so word order and glue
    words no longer split groups)."""
    return " ".join(title_tokens(title_en))[:500]


def gtin_group_id(gtin: str) -> uuid.UUID:
    """Deterministic group id for a GTIN ("gtin:" prefix — ':' cannot occur
    in brand_model "brand|code" keys, so the id spaces are disjoint)."""
    return uuid.uuid5(MATCH_NAMESPACE, f"gtin:{gtin.strip()}")


def title_group_id(title_en: str, product_type_en: str | None) -> uuid.UUID:
    """Deterministic group id for the normalized EN title key within a type."""
    type_key = (product_type_en or "").strip().lower()
    return uuid.uuid5(
        MATCH_NAMESPACE, f"title2:{type_key}:{_normalize_title_key(title_en)}"
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


def fetch_title_groups_sync(
    limit: int,
) -> list[tuple[str, str | None, str]]:
    """(group_id, product_type_en, representative title_en) per title-method
    group — deterministic representative (min title_en) and ordering."""
    from sqlalchemy import func as sa_func

    from app.database import sync_session_factory

    db = sync_session_factory()
    try:
        rows = db.execute(
            select(
                DimProduct.match_group_id,
                DimProduct.product_type_en,
                sa_func.min(DimProduct.title_en).label("rep"),
            )
            .where(
                DimProduct.is_active,
                DimProduct.match_method.in_(
                    [METHOD_TITLE_EXACT, METHOD_TITLE_SIM]
                ),
            )
            .group_by(DimProduct.match_group_id, DimProduct.product_type_en)
            .order_by(DimProduct.product_type_en, DimProduct.match_group_id)
            .limit(limit)
        ).all()
        return [(str(gid), type_en, rep) for gid, type_en, rep in rows if rep]
    finally:
        db.close()


def fetch_group_member_ids_sync(group_id: str) -> list[str]:
    from app.database import sync_session_factory

    db = sync_session_factory()
    try:
        rows = db.execute(
            select(DimProduct.id).where(
                DimProduct.match_group_id == uuid.UUID(group_id)
            )
        ).scalars()
        return [str(pid) for pid in rows]
    finally:
        db.close()


UNMATCHED_RESWEEP_ROWS = 1_000
_RESWEEP_CURSOR_KEY = "match:resweep:cursor"


def fetch_unmatched_after_sync(
    cursor_id: str | None, limit: int
) -> list[tuple[str, str | None, str | None, str | None, str | None]]:
    """Page of 'unmatched' rows after the cursor id (wrapping full cycle)."""
    from app.database import sync_session_factory

    db = sync_session_factory()
    try:
        stmt = (
            select(
                DimProduct.id,
                DimProduct.name_normalized,
                DimProduct.sku_universal,
                DimProduct.title_en,
                DimProduct.product_type_en,
            )
            .where(DimProduct.is_active, DimProduct.match_method == METHOD_UNMATCHED)
            .order_by(DimProduct.id)
            .limit(limit)
        )
        if cursor_id:
            stmt = stmt.where(DimProduct.id > uuid.UUID(cursor_id))
        rows = db.execute(stmt).all()
        return [
            (str(pid), name, sku, title_en, type_en)
            for pid, name, sku, title_en, type_en in rows
        ]
    finally:
        db.close()


def run_unmatched_resweep(known_brands: frozenset[str]) -> dict[str, int]:
    """Re-extract signatures for 'unmatched' rows in a wrapping cycle.

    Harvest keeps replacing slug-junk names ("pb00613262.html") with real
    card titles via product_enrich — rows written off as unmatched become
    matchable later. 1000 rows/tick cycles the whole unmatched set every
    ~1-2 days; only rows that now match are rewritten.
    """
    from app.modules.scraper.pipeline.worker_log_relay import _get_redis

    cursor: str | None = None
    client = None
    try:
        client = _get_redis()
        raw = client.get(_RESWEEP_CURSOR_KEY)
        cursor = raw.decode() if isinstance(raw, bytes) else raw
    except Exception:
        client = None

    rows = fetch_unmatched_after_sync(cursor, UNMATCHED_RESWEEP_ROWS)
    wrapped = False
    if not rows and cursor:
        wrapped = True
        rows = fetch_unmatched_after_sync(None, UNMATCHED_RESWEEP_ROWS)

    payloads: list[dict[str, Any]] = []
    for product_id, name, sku, title_en, type_en in rows:
        signature = extract_signature(name, known_brands)
        fields = build_match_fields(
            product_id,
            signature,
            sku_universal=sku,
            title_en=title_en,
            product_type_en=type_en,
        )
        if fields["match_method"] != METHOD_UNMATCHED:
            payloads.append(fields)

    upgraded = 0
    if payloads:
        upgraded = write_match_results_sync(payloads)
    if client is not None and rows:
        try:
            client.set(_RESWEEP_CURSOR_KEY, rows[-1][0])
        except Exception:
            pass
    return {
        "resweep_scanned": len(rows),
        "resweep_upgraded": upgraded,
        "resweep_wrapped": int(wrapped),
    }


TYPE_SPLIT_GROUPS_CAP = 300


def run_type_split_pass() -> dict[str, int]:
    """Split groups whose members carry CONFLICTING product_type_en.

    Accessories mentioning a device ("Magic Keyboard fur iPad Air 11")
    join the device's group through a code like air11. Once enrichment
    types both sides, the conflict is visible: minority types get the
    deterministic sub-group uuid5("split:<gid>:<type>") — repeated passes
    converge, and a future member of either type lands consistently.
    """
    from sqlalchemy import func as sa_func

    from app.database import sync_session_factory

    db = sync_session_factory()
    try:
        rows = db.execute(
            select(
                DimProduct.match_group_id,
                DimProduct.product_type_en,
                sa_func.count().label("n"),
            )
            .where(
                DimProduct.is_active,
                DimProduct.match_group_id.isnot(None),
                DimProduct.product_type_en.isnot(None),
            )
            .group_by(DimProduct.match_group_id, DimProduct.product_type_en)
        ).all()
    finally:
        db.close()

    by_group: dict[str, list[tuple[str, int]]] = {}
    for gid, type_en, n in rows:
        by_group.setdefault(str(gid), []).append(
            ((type_en or "").strip().lower(), int(n))
        )

    conflicted = {
        gid: types for gid, types in by_group.items() if len(types) >= 2
    }
    payloads: list[dict[str, Any]] = []
    split_groups = 0
    for gid in sorted(conflicted)[:TYPE_SPLIT_GROUPS_CAP]:
        types = conflicted[gid]
        # Dominant: max member count, tie -> lexicographic min (deterministic).
        dominant = sorted(types, key=lambda t: (-t[1], t[0]))[0][0]
        split_groups += 1
        for type_key, _n in types:
            if type_key == dominant:
                continue
            new_gid = uuid.uuid5(MATCH_NAMESPACE, f"split:{gid}:{type_key}")
            member_ids = _fetch_group_type_member_ids(gid, type_key)
            for product_id in member_ids:
                payloads.append(
                    {"id": product_id, "match_group_id": str(new_gid)}
                )
    moved = write_match_results_sync(payloads) if payloads else 0
    return {"split_groups": split_groups, "split_moved": moved}


def _fetch_group_type_member_ids(group_id: str, type_key: str) -> list[str]:
    from sqlalchemy import func as sa_func

    from app.database import sync_session_factory

    db = sync_session_factory()
    try:
        rows = db.execute(
            select(DimProduct.id).where(
                DimProduct.match_group_id == uuid.UUID(group_id),
                sa_func.lower(sa_func.btrim(DimProduct.product_type_en))
                == type_key,
            )
        ).scalars()
        return [str(pid) for pid in rows]
    finally:
        db.close()


def run_title_merge_pass() -> dict[str, int]:
    """M2b: merge near-identical title groups within a type block.

    Sorted-neighborhood over the normalized token key (window
    TITLE_MERGE_WINDOW); a pair scoring >= TITLE_SIM_THRESHOLD with no unit
    conflict merges into min(group_id) — the deterministic merge target, so
    repeated passes over the same data converge to the same groups.
    """
    groups = fetch_title_groups_sync(TITLE_MERGE_GROUPS_CAP)
    if len(groups) < 2:
        return {"title_groups": len(groups), "merged_groups": 0, "moved_rows": 0}

    # (type, token_key, tokens, group_id) sorted for neighborhood scanning
    keyed = sorted(
        (
            (
                (type_en or "").strip().lower(),
                " ".join(title_tokens(rep)),
                title_tokens(rep),
                gid,
            )
            for gid, type_en, rep in groups
        ),
        key=lambda item: (item[0], item[1], item[3]),
    )

    merged_into: dict[str, str] = {}

    def _resolve(gid: str) -> str:
        while gid in merged_into:
            gid = merged_into[gid]
        return gid

    for i, (type_a, _key_a, toks_a, gid_a) in enumerate(keyed):
        for j in range(i + 1, min(i + 1 + TITLE_MERGE_WINDOW, len(keyed))):
            type_b, _key_b, toks_b, gid_b = keyed[j]
            if type_b != type_a:
                break
            ra, rb = _resolve(gid_a), _resolve(gid_b)
            if ra == rb:
                continue
            if score_titles(toks_a, toks_b) >= TITLE_SIM_THRESHOLD:
                winner, loser = (ra, rb) if ra < rb else (rb, ra)
                merged_into[loser] = winner

    moved = 0
    payloads: list[dict[str, Any]] = []
    for loser in merged_into:
        winner = _resolve(loser)
        for product_id in fetch_group_member_ids_sync(loser):
            payloads.append(
                {
                    "id": product_id,
                    "match_group_id": winner,
                    "match_method": METHOD_TITLE_SIM,
                    "match_confidence": CONFIDENCE_TITLE_SIM,
                }
            )
            moved += 1
    if payloads:
        write_match_results_sync(payloads)
    return {
        "title_groups": len(groups),
        "merged_groups": len(merged_into),
        "moved_rows": moved,
    }


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
    merge_stats = run_title_merge_pass()
    resweep_stats = run_unmatched_resweep(known_brands)
    split_stats = run_type_split_pass()
    summary = {
        "scanned": len(pending),
        "matched": matched,
        "unmatched": len(pending) - matched,
        "gtin_swept": len(gtin_swept),
        "title_swept": len(title_swept),
        "written": written,
        **merge_stats,
        **resweep_stats,
        **split_stats,
    }
    slog.info("product_match_tick_done", **summary)
    return summary
