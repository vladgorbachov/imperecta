"""Gated pool persistence for discovery (dim_product + fact_listing pairs)."""

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy.exc import DBAPIError

from app.database import sync_session_factory
from app.modules.data_firewall.firewall import evaluate_market
from app.modules.data_firewall.signing import SignedRecord
from app.modules.persist.gate_rpc import GateRpcError, exec_write_records, exec_write_rows
from app.modules.persist.writer import PersistContext, write_sync

# Pairs per pipelined gate statement: two round-trips (products, then
# listings — FK order) instead of two per pair. Bounds statement size and
# the blast radius of a mid-chunk failure.
FAST_WRITE_CHUNK_PAIRS = 100


@dataclass(frozen=True)
class PoolInsertDTO:
    """One dim_product + fact_listing pair for gated pool persistence."""

    marketplace_id: UUID
    dim_product: dict[str, Any]
    fact_listing: dict[str, Any]


@dataclass(frozen=True)
class PoolWriteResult:
    """Outcome of a batched sync pool write through data_firewall."""

    inserted: int
    rejected: int


@dataclass(frozen=True)
class _SignedPair:
    dto: PoolInsertDTO
    product: SignedRecord
    listing: SignedRecord


def _evaluate_pairs(
    db: Any,
    dtos: list[PoolInsertDTO],
) -> tuple[list[_SignedPair], int]:
    """Run both firewall evaluations per DTO before anything is written.

    Nothing touches the pool tables until a pair carries two signed records,
    so a rejected listing can never leave an orphan dim_product behind.
    """
    pairs: list[_SignedPair] = []
    rejected = 0
    for dto in dtos:
        outcome_product = evaluate_market(
            dto.dim_product,
            table="dim_product",
            db=db,
            reject_source="discovery",
        )
        if not outcome_product.passed or outcome_product.signed_record is None:
            rejected += 1
            continue
        outcome_listing = evaluate_market(
            dto.fact_listing,
            table="fact_listing",
            db=db,
            reject_source="discovery",
        )
        if not outcome_listing.passed or outcome_listing.signed_record is None:
            rejected += 1
            continue
        pairs.append(
            _SignedPair(
                dto=dto,
                product=outcome_product.signed_record,
                listing=outcome_listing.signed_record,
            )
        )
    return pairs, rejected


def _write_pair_slow(db: Any, pair: _SignedPair) -> bool:
    """Per-pair savepoint write — the pre-pipelining path, kept as fallback."""
    nested = db.begin_nested()
    try:
        ctx = PersistContext(
            source="discovery",
            marketplace_id=pair.dto.marketplace_id,
        )
        if not write_sync(db, pair.product, ctx=ctx):
            nested.rollback()
            return False
        if not write_sync(db, pair.listing, ctx=ctx):
            nested.rollback()
            return False
        nested.commit()
        return True
    except (GateRpcError, DBAPIError):
        # A pair the gate refuses one-by-one (typically a url_hash / id
        # duplicate from a concurrent shard racing on the same URL) is a
        # rejected pair, not a failed batch: fan-out shards overlap on
        # purpose and must stay idempotent. Anything else propagates.
        nested.rollback()
        return False
    except Exception:
        nested.rollback()
        raise


def write_pool_dtos_sync(dtos: list[PoolInsertDTO]) -> PoolWriteResult:
    """Persist discovery pool rows via evaluate_market -> gate.exec_write.

    Runs inside asyncio.to_thread — never on the orchestrator's AsyncSession.
    Every pair is evaluated (and signed) up front; signed chunks are then
    pipelined through exec_write_records — two round-trips per chunk
    (all products first, then all listings, preserving the FK order) instead
    of two per pair. A chunk that fails mid-statement rolls back to its
    savepoint and is retried pair-by-pair via write_sync, so one bad row
    (e.g. a concurrent url_hash duplicate) only costs its own chunk speed.
    One commit per batch.
    """
    if not dtos:
        return PoolWriteResult(inserted=0, rejected=0)

    db = sync_session_factory()
    inserted = 0
    rejected = 0
    try:
        pairs, rejected = _evaluate_pairs(db, dtos)

        for start in range(0, len(pairs), FAST_WRITE_CHUNK_PAIRS):
            chunk = pairs[start : start + FAST_WRITE_CHUNK_PAIRS]
            nested = db.begin_nested()
            try:
                # Set-based path (069): one INSERT per table per chunk. The
                # per-record pipeline stays as the fallback for chunks the
                # gate refuses as a set (heterogeneous rows, a duplicate).
                exec_write_rows(db, "dim_product", [pair.product for pair in chunk])
                exec_write_rows(db, "fact_listing", [pair.listing for pair in chunk])
                nested.commit()
                inserted += len(chunk)
            except (GateRpcError, DBAPIError):
                nested.rollback()
                for pair in chunk:
                    if _write_pair_slow(db, pair):
                        inserted += 1
                    else:
                        rejected += 1

        db.commit()
        return PoolWriteResult(inserted=inserted, rejected=rejected)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
