"""Taxonomy enrichment (P13): categories → name_en, products → type + EN layer.

Batch LLM calls (cheapest Claude family), never per request. All writes go
through the data_firewall gate: dim_category via the ``category_translate``
door, dim_product via the existing ``product_enrich`` door. Honest-data rule:
an item the model failed to answer for stays NULL — no fabricated values.
"""

from __future__ import annotations

import json
import re
from typing import Any

import structlog
from sqlalchemy import select

from app.models.dimensions import DimCategory, DimProduct
from app.models.facts import FactListing
from app.modules.data_firewall.update_validator import authorize_scrape_update
from app.modules.persist.writer import PersistContext, write_sync

slog = structlog.get_logger(__name__)

CATEGORY_BATCH_SIZE = 80
PRODUCT_BATCH_SIZE = 60
ENRICH_MAX_TOKENS = 4000

_CATEGORY_PROMPT = """Translate e-commerce category names to English.
Input is a JSON object mapping an index to a category name in any language.
Reply with ONLY a JSON object mapping the same indexes to the English
translation (short, natural category label, Title Case). No commentary.

{payload}"""

_PRODUCT_PROMPT = """You classify e-commerce product titles.
Input is a JSON object mapping an index to a product title (any language).
For each index reply with:
- "type": the product type in the TITLE'S OWN language — one or a few words,
  narrower than a category (e.g. "sülearvuti", "ceas inteligent").
- "type_en": the same product type in English (e.g. "laptop", "smartwatch").
- "title_en": the full title translated to English (keep brand/model codes).
If a title is too ambiguous to classify, OMIT that index entirely.
Reply with ONLY a JSON object: {{"<index>": {{"type": "...", "type_en": "...",
"title_en": "..."}}}}. No commentary.

{payload}"""


def _extract_json(text: str) -> dict[str, Any]:
    """Parse the model reply as JSON, tolerating code fences."""
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.MULTILINE)
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start < 0 or end <= start:
        return {}
    try:
        parsed = json.loads(cleaned[start : end + 1])
    except ValueError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def build_category_prompt(names_by_index: dict[str, str]) -> str:
    return _CATEGORY_PROMPT.format(
        payload=json.dumps(names_by_index, ensure_ascii=False)
    )


def build_product_prompt(titles_by_index: dict[str, str]) -> str:
    return _PRODUCT_PROMPT.format(
        payload=json.dumps(titles_by_index, ensure_ascii=False)
    )


def parse_category_reply(text: str, names_by_index: dict[str, str]) -> dict[str, str]:
    """index -> name_en for indexes present in both input and reply."""
    parsed = _extract_json(text)
    out: dict[str, str] = {}
    for idx, value in parsed.items():
        if idx not in names_by_index:
            continue
        if isinstance(value, str) and value.strip():
            out[idx] = value.strip()[:200]
    return out


def _capitalize_first(value: str) -> str:
    """Uppercase only the first letter — 'macbook stand' → 'Macbook stand',
    but 'iPhone case' keeps its inner casing (str.capitalize would not)."""
    return value[:1].upper() + value[1:]


def parse_product_reply(
    text: str, titles_by_index: dict[str, str]
) -> dict[str, dict[str, str]]:
    """index -> {product_type, product_type_en, title_en}; partial rows dropped.

    Type names are stored with a leading capital (user rule: the Type column
    always shows a capitalized name) — normalized at write time so every
    consumer (list API, CSV export, future readers) agrees.
    """
    parsed = _extract_json(text)
    out: dict[str, dict[str, str]] = {}
    for idx, value in parsed.items():
        if idx not in titles_by_index or not isinstance(value, dict):
            continue
        type_local = str(value.get("type") or "").strip()
        type_en = str(value.get("type_en") or "").strip()
        title_en = str(value.get("title_en") or "").strip()
        if not type_en:
            continue
        row: dict[str, str] = {"product_type_en": _capitalize_first(type_en[:200])}
        if type_local:
            row["product_type"] = _capitalize_first(type_local[:200])
        if title_en:
            row["title_en"] = title_en[:500]
        out[idx] = row
    return out


def fetch_untranslated_categories_sync(limit: int) -> list[tuple[str, str]]:
    """[(id, name)] of active categories missing name_en."""
    from app.database import sync_session_factory

    db = sync_session_factory()
    try:
        rows = db.execute(
            select(DimCategory.id, DimCategory.name)
            .where(DimCategory.name_en.is_(None))
            .order_by(DimCategory.name)
            .limit(limit)
        ).all()
        return [(str(r[0]), r[1]) for r in rows]
    finally:
        db.close()


REUSE_DONOR_BATCH = 400


def reuse_existing_enrichment_sync(limit: int) -> int:
    """Copy type/EN fields from an already-enriched identical product — free.

    Identity = same name_normalized. Runs BEFORE any LLM batch so duplicate
    products never spend AI credits. Two bounded phases (the single
    self-join let the planner drive from the 1.45M untyped side — observed
    statement timeout live): phase 1 reads a slice of DONORS off the tiny
    partial index (migration 058), phase 2 fetches untyped twins for those
    exact names. Each copy still goes through the product_enrich gate door.
    """
    from app.database import sync_session_factory

    db = sync_session_factory()
    try:
        donors = db.execute(
            select(
                DimProduct.name_normalized,
                DimProduct.product_type,
                DimProduct.product_type_en,
                DimProduct.title_en,
            )
            .where(DimProduct.product_type_en.isnot(None))
            .distinct(DimProduct.name_normalized)
            .order_by(DimProduct.name_normalized)
            .limit(REUSE_DONOR_BATCH)
        ).all()
        if not donors:
            return 0
        by_name = {row[0]: row for row in donors}
        targets = db.execute(
            select(DimProduct.id, DimProduct.name_normalized)
            .where(DimProduct.name_normalized.in_(list(by_name)))
            .where(DimProduct.product_type_en.is_(None))
            .limit(limit)
        ).all()
    finally:
        db.close()

    updates: dict[str, dict[str, str]] = {}
    for product_id, name_norm in targets:
        _, ptype, ptype_en, title_en = by_name[name_norm]
        columns: dict[str, str] = {"product_type_en": ptype_en}
        if ptype:
            columns["product_type"] = ptype
        if title_en:
            columns["title_en"] = title_en
        updates[str(product_id)] = columns
    return write_product_types_sync(updates)


def fetch_untyped_products_sync(limit: int) -> list[tuple[str, str]]:
    """[(id, name)] of products still missing a type, priced listings first.

    The Products page defaults to priced rows, so enriching priced products
    first fixes what users actually see; categorized-but-unpriced products
    follow, the long skeleton tail comes last as budget allows.
    """
    from app.database import sync_session_factory

    db = sync_session_factory()
    try:
        # Bounded phases (a DISTINCT ON over the 1.45M untyped set sorts the
        # world): drive from priced listings, dedupe names in Python so
        # identical titles never spend two LLM slots — the reuse pass
        # propagates the answer to the twins.
        priced_ids = [
            r[0]
            for r in db.execute(
                select(FactListing.product_id)
                .where(FactListing.is_active)
                .where(FactListing.last_price.isnot(None))
                .limit(20_000)
            )
        ]
        rows: list = []
        if priced_ids:
            rows = db.execute(
                select(DimProduct.id, DimProduct.name, DimProduct.name_normalized)
                .where(DimProduct.id.in_(priced_ids))
                .where(DimProduct.product_type_en.is_(None))
                .limit(limit * 4)
            ).all()
        if len(rows) < limit:
            rows += db.execute(
                select(DimProduct.id, DimProduct.name, DimProduct.name_normalized)
                .where(DimProduct.category_id.isnot(None))
                .where(DimProduct.product_type_en.is_(None))
                .limit(limit * 4)
            ).all()
        seen_names: set[str] = set()
        out: list[tuple[str, str]] = []
        for pid, name, name_norm in rows:
            if name_norm in seen_names:
                continue
            seen_names.add(name_norm)
            out.append((str(pid), name))
            if len(out) >= limit:
                break
        return out
    finally:
        db.close()


def _gated_update_sync(table: str, kind: str, fields: dict[str, Any], source: str) -> bool:
    from app.database import sync_session_factory

    db = sync_session_factory()
    try:
        outcome = authorize_scrape_update(
            table=table, kind=kind, fields=fields, db=db, reject_source=source
        )
        if not outcome.passed or outcome.signed_record is None:
            db.rollback()
            return False
        result = write_sync(db, outcome.signed_record, ctx=PersistContext(source=source))
        if not result.ok:
            db.rollback()
            return False
        db.commit()
        return True
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def write_category_translations_sync(updates: dict[str, str]) -> int:
    """Gate-write {category_id: name_en}; returns rows written."""
    written = 0
    for category_id, name_en in updates.items():
        if _gated_update_sync(
            "dim_category",
            "category_translate",
            {"id": category_id, "name_en": name_en},
            "taxonomy_enrich",
        ):
            written += 1
    return written


def write_product_types_sync(updates: dict[str, dict[str, str]]) -> int:
    """Gate-write {product_id: {product_type, product_type_en, title_en}}."""
    written = 0
    for product_id, columns in updates.items():
        if _gated_update_sync(
            "dim_product",
            "product_enrich",
            {"id": product_id, **columns},
            "taxonomy_enrich",
        ):
            written += 1
    return written
