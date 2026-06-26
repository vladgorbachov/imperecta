"""Gated pool persistence for discovery (dim_product + fact_listing pairs)."""

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from app.database import sync_session_factory
from app.modules.data_firewall.firewall import evaluate_market
from app.modules.persist.writer import PersistContext, write_sync


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


def write_pool_dtos_sync(dtos: list[PoolInsertDTO]) -> PoolWriteResult:
    """Persist discovery pool rows via evaluate_market -> write_sync on a sync Session.

    Runs inside asyncio.to_thread — never on DiscoveryCrawler's AsyncSession.
    One commit per batch; each DTO pair uses a nested savepoint so a failed
    listing gate/write does not leave an orphan dim_product in the batch.
    """
    if not dtos:
        return PoolWriteResult(inserted=0, rejected=0)

    db = sync_session_factory()
    inserted = 0
    rejected = 0
    try:
        for dto in dtos:
            nested = db.begin_nested()
            try:
                product_ctx = PersistContext(
                    source="discovery",
                    marketplace_id=dto.marketplace_id,
                )
                outcome_product = evaluate_market(
                    dto.dim_product,
                    table="dim_product",
                    db=db,
                    reject_source="discovery",
                )
                if (
                    not outcome_product.passed
                    or outcome_product.signed_record is None
                ):
                    nested.rollback()
                    rejected += 1
                    continue

                if not write_sync(
                    db,
                    outcome_product.signed_record,
                    ctx=product_ctx,
                ):
                    nested.rollback()
                    rejected += 1
                    continue

                listing_ctx = PersistContext(
                    source="discovery",
                    marketplace_id=dto.marketplace_id,
                )
                outcome_listing = evaluate_market(
                    dto.fact_listing,
                    table="fact_listing",
                    db=db,
                    reject_source="discovery",
                )
                if (
                    not outcome_listing.passed
                    or outcome_listing.signed_record is None
                ):
                    nested.rollback()
                    rejected += 1
                    continue

                if not write_sync(
                    db,
                    outcome_listing.signed_record,
                    ctx=listing_ctx,
                ):
                    nested.rollback()
                    rejected += 1
                    continue

                nested.commit()
                inserted += 1
            except Exception:
                nested.rollback()
                raise

        db.commit()
        return PoolWriteResult(inserted=inserted, rejected=rejected)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
