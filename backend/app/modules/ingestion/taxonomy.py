"""Brand / category taxonomy upsert via the META gate (parser completeness).

Scrape enrichment resolves extracted brand names and breadcrumb paths into
``dim_brand`` / ``dim_category`` rows. Reads are operational SELECTs next to
the consumer; every write goes through ``evaluate_market`` -> ``write_sync``
-> ``gate.exec_write``. SELECT-first keeps the common path insert-free; a
concurrent insert race resolves by re-SELECT after the rejected write.
"""

from __future__ import annotations

import re
from typing import Any
from uuid import UUID, uuid4

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.dimensions import DimBrand, DimCategory
from app.modules.data_firewall.firewall import evaluate_market
from app.modules.persist.gate_rpc import GateRpcError
from app.modules.persist.writer import PersistContext, write_sync

slog = structlog.get_logger(__name__)

_MAX_NAME_LEN = 200
_MAX_CATEGORY_DEPTH = 6
_PATH_SEPARATOR = " > "


def _normalize_taxonomy_name(raw: str) -> str:
    """Lowercase, collapse whitespace — dedupe key for dim_brand.name_normalized."""
    s = (raw or "").lower().strip()
    s = re.sub(r"\s+", " ", s)
    return s[:_MAX_NAME_LEN]


def _slugify(raw: str) -> str:
    """Deterministic slug: lowercase word chars (unicode) joined by hyphens."""
    s = (raw or "").lower().strip()
    s = re.sub(r"[^\w]+", "-", s, flags=re.UNICODE).strip("-")
    s = re.sub(r"-{2,}", "-", s)
    return s[:_MAX_NAME_LEN]


def _gate_insert(
    db: Session,
    *,
    table: str,
    fields: dict[str, Any],
    reject_source: str,
) -> bool:
    """Sign via the META door and write; False on reject or RPC failure."""
    outcome = evaluate_market(
        fields,
        table=table,
        operation="insert",
        db=db,
        reject_source=reject_source,
    )
    if not outcome.passed or outcome.signed_record is None:
        return False
    try:
        result = write_sync(
            db,
            outcome.signed_record,
            ctx=PersistContext(source=reject_source),
        )
    except GateRpcError as exc:
        # Unique-key race with a concurrent worker: caller re-SELECTs.
        slog.warning(
            "taxonomy_gate_insert_conflict",
            table=table,
            kind=exc.kind,
        )
        return False
    return bool(result.ok)


def ensure_brand(db: Session, brand_name: str) -> UUID | None:
    """Return dim_brand.id for the extracted brand, inserting through the gate."""
    name = (brand_name or "").strip()[:_MAX_NAME_LEN]
    if not name:
        return None
    normalized = _normalize_taxonomy_name(name)
    slug = _slugify(name)
    if not normalized or not slug:
        return None

    existing = db.execute(
        select(DimBrand.id).where(DimBrand.name_normalized == normalized),
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    brand_id = uuid4()
    inserted = _gate_insert(
        db,
        table="dim_brand",
        fields={
            "id": str(brand_id),
            "name": name,
            "slug": slug,
            "name_normalized": normalized,
            "is_active": True,
        },
        reject_source="ingestion_brand",
    )
    if inserted:
        return brand_id
    return db.execute(
        select(DimBrand.id).where(DimBrand.name_normalized == normalized),
    ).scalar_one_or_none()


def ensure_category_chain(db: Session, category_path: list[str]) -> UUID | None:
    """Return the leaf dim_category.id for a breadcrumb path, inserting missing
    ancestors through the gate. Slug key = slugified cumulative path, so equal
    leaf names under different parents stay distinct rows."""
    cleaned = [
        p.strip()[:_MAX_NAME_LEN]
        for p in (category_path or [])
        if isinstance(p, str) and p.strip()
    ][:_MAX_CATEGORY_DEPTH]
    if not cleaned:
        return None

    parent_id: UUID | None = None
    cumulative: list[str] = []
    for level, name in enumerate(cleaned, start=1):
        cumulative.append(name)
        path_str = _PATH_SEPARATOR.join(cumulative)
        slug = _slugify(path_str)
        if not slug:
            return None

        existing = db.execute(
            select(DimCategory.id).where(DimCategory.slug == slug),
        ).scalar_one_or_none()
        if existing is not None:
            parent_id = existing
            continue

        category_id = uuid4()
        inserted = _gate_insert(
            db,
            table="dim_category",
            fields={
                "id": str(category_id),
                "name": name,
                "slug": slug,
                "parent_id": str(parent_id) if parent_id is not None else None,
                "level": level,
                "path": path_str,
                "is_active": True,
                "product_count": 0,
            },
            reject_source="ingestion_category",
        )
        if inserted:
            parent_id = category_id
            continue
        refetched = db.execute(
            select(DimCategory.id).where(DimCategory.slug == slug),
        ).scalar_one_or_none()
        if refetched is None:
            return None
        parent_id = refetched
    return parent_id
