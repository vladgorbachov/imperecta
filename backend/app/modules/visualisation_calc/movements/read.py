"""Operational sync SELECT for movement candidates (service-data, no access-log)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.models.dimensions import DimCategory, DimCountry, DimMarketplace, DimProduct
from app.models.facts import FactListing, FactPrice
from app.modules.visualisation_calc.movements.schemas import MovementsFilters

_PERIOD_DELTAS: dict[str, timedelta] = {
    "24h": timedelta(hours=24),
    "7d": timedelta(days=7),
    "30d": timedelta(days=30),
}


@dataclass(frozen=True)
class MoverReadRow:
    """Typed read row — not an ORM object."""

    listing_id: UUID
    product_name: str
    image_url: str | None
    marketplace_id: UUID
    marketplace_name: str
    marketplace_domain: str | None
    country_code: str
    country_name: str
    category_id: UUID | None
    category_name: str | None
    new_price: Decimal
    currency_code: str
    price_change_pct: Decimal
    changed_at: datetime
    prior_fact_price: Decimal | None


@dataclass(frozen=True)
class MoversCoverageCounts:
    """Coverage counters from a separate operational COUNT query."""

    listings_total: int
    listings_with_change: int


def _window_cutoff(period: str, *, now: datetime | None = None) -> datetime:
    """Return UTC cutoff for last_price_changed_at window filters."""
    anchor = now or datetime.now(tz=UTC)
    try:
        delta = _PERIOD_DELTAS[period]
    except KeyError as exc:
        raise ValueError(f"unsupported movements period: {period}") from exc
    return anchor - delta


def _ranked_fact_prices_subquery():
    """Row-number partition mirroring product_pool._latest_price_change_subquery."""
    rn = func.row_number().over(
        partition_by=FactPrice.listing_id,
        order_by=desc(FactPrice.date_id),
    ).label("rn")
    return (
        select(
            FactPrice.listing_id,
            FactPrice.price,
            FactPrice.currency_code,
            FactPrice.price_change_pct,
            FactPrice.date_id,
            rn,
        )
    ).subquery()


def _latest_fact_price_subquery():
    """Latest fact_price row per listing (rn = 1)."""
    ranked = _ranked_fact_prices_subquery()
    return (
        select(
            ranked.c.listing_id,
            ranked.c.price,
            ranked.c.currency_code,
            ranked.c.price_change_pct,
            ranked.c.date_id,
        ).where(ranked.c.rn == 1)
    ).subquery()


def _prior_fact_price_subquery():
    """Second-latest fact_price row per listing (rn = 2) for honest old_price."""
    ranked = _ranked_fact_prices_subquery()
    return (
        select(
            ranked.c.listing_id,
            ranked.c.price.label("prior_fact_price"),
        ).where(ranked.c.rn == 2)
    ).subquery()


def _apply_entity_filters(stmt, filters: MovementsFilters):
    """Country / marketplace / category filters on the join graph."""
    if filters.country_code:
        stmt = stmt.where(
            DimMarketplace.country_code == filters.country_code.strip().upper()
        )
    if filters.marketplace_id is not None:
        stmt = stmt.where(FactListing.marketplace_id == filters.marketplace_id)
    if filters.category_id is not None:
        stmt = stmt.where(DimProduct.category_id == filters.category_id)
    return stmt


def _base_mover_stmt(filters: MovementsFilters, *, cutoff: datetime):
    """Shared join graph for movers reads."""
    latest_fp = _latest_fact_price_subquery()
    prior_fp = _prior_fact_price_subquery()
    stmt = (
        select(
            FactListing.id.label("listing_id"),
            DimProduct.name.label("product_name"),
            DimProduct.image_url,
            FactListing.marketplace_id,
            DimMarketplace.name.label("marketplace_name"),
            DimMarketplace.domain.label("marketplace_domain"),
            DimMarketplace.country_code,
            DimCountry.name.label("country_name"),
            DimProduct.category_id,
            DimCategory.name.label("category_name"),
            latest_fp.c.price.label("new_price"),
            latest_fp.c.currency_code,
            latest_fp.c.price_change_pct,
            FactListing.last_price_changed_at.label("changed_at"),
            prior_fp.c.prior_fact_price,
        )
        .select_from(FactListing)
        .join(DimProduct, FactListing.product_id == DimProduct.id)
        .join(DimMarketplace, FactListing.marketplace_id == DimMarketplace.id)
        .join(DimCountry, DimMarketplace.country_code == DimCountry.country_code)
        .outerjoin(DimCategory, DimProduct.category_id == DimCategory.id)
        .join(latest_fp, latest_fp.c.listing_id == FactListing.id)
        .outerjoin(prior_fp, prior_fp.c.listing_id == FactListing.id)
        .where(FactListing.is_active.is_(True))
        .where(FactListing.last_price_changed_at.is_not(None))
        .where(FactListing.last_price_changed_at >= cutoff)
        .where(latest_fp.c.price_change_pct.is_not(None))
    )
    return _apply_entity_filters(stmt, filters)


def _row_to_mover_read_row(row: Any) -> MoverReadRow:
    return MoverReadRow(
        listing_id=row.listing_id,
        product_name=row.product_name,
        image_url=row.image_url,
        marketplace_id=row.marketplace_id,
        marketplace_name=row.marketplace_name,
        marketplace_domain=row.marketplace_domain,
        country_code=row.country_code,
        country_name=row.country_name,
        category_id=row.category_id,
        category_name=row.category_name,
        new_price=Decimal(str(row.new_price)),
        currency_code=str(row.currency_code),
        price_change_pct=Decimal(str(row.price_change_pct)),
        changed_at=row.changed_at,
        prior_fact_price=(
            Decimal(str(row.prior_fact_price))
            if row.prior_fact_price is not None
            else None
        ),
    )


def read_mover_rows(
    filters: MovementsFilters,
    db: Session,
    *,
    now: datetime | None = None,
) -> list[MoverReadRow]:
    """Operational sync SELECT returning typed mover candidate rows.

    Excludes NULL price_change_pct (honest — no movement signal yet).
    Window basis: fact_listing.last_price_changed_at (actual price changes only).
    """
    cutoff = _window_cutoff(filters.period, now=now)
    stmt = _base_mover_stmt(filters, cutoff=cutoff)
    rows = db.execute(stmt).all()
    return [_row_to_mover_read_row(row) for row in rows]


def read_coverage_counts(
    filters: MovementsFilters,
    db: Session,
    *,
    now: datetime | None = None,
) -> MoversCoverageCounts:
    """Count listings in the window vs those with a non-NULL latest price_change_pct."""
    cutoff = _window_cutoff(filters.period, now=now)
    latest_fp = _latest_fact_price_subquery()

    total_stmt = (
        select(func.count())
        .select_from(FactListing)
        .join(DimProduct, FactListing.product_id == DimProduct.id)
        .join(DimMarketplace, FactListing.marketplace_id == DimMarketplace.id)
        .where(FactListing.is_active.is_(True))
        .where(FactListing.last_price_changed_at.is_not(None))
        .where(FactListing.last_price_changed_at >= cutoff)
    )
    total_stmt = _apply_entity_filters(total_stmt, filters)
    listings_total = int(db.execute(total_stmt).scalar_one())

    with_change_stmt = (
        select(func.count())
        .select_from(FactListing)
        .join(DimProduct, FactListing.product_id == DimProduct.id)
        .join(DimMarketplace, FactListing.marketplace_id == DimMarketplace.id)
        .join(latest_fp, latest_fp.c.listing_id == FactListing.id)
        .where(FactListing.is_active.is_(True))
        .where(FactListing.last_price_changed_at.is_not(None))
        .where(FactListing.last_price_changed_at >= cutoff)
        .where(latest_fp.c.price_change_pct.is_not(None))
    )
    with_change_stmt = _apply_entity_filters(with_change_stmt, filters)
    listings_with_change = int(db.execute(with_change_stmt).scalar_one())

    return MoversCoverageCounts(
        listings_total=listings_total,
        listings_with_change=listings_with_change,
    )
