"""HTTP routes for visualisation_calc widgets (movements KPIs and feed)."""

from __future__ import annotations

import asyncio
from decimal import Decimal
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Query

from app.common.deps import CurrentUser, DbSession
from app.database import sync_session_factory
from app.modules.currency import CurrencyConverter, normalize_display_currency
from app.modules.visualisation_calc.movements.read import (
    read_coverage_counts,
    read_mover_rows,
)
from app.modules.visualisation_calc.movements.schemas import (
    MovementsFilters,
    MoversCoverageMeta,
    MoversKpi,
    MoversPage,
    MoversSummary,
)
from app.modules.visualisation_calc.movements.service import MovementsCalc, apply_display_currency

router = APIRouter(prefix="/markets", tags=["markets"])


def _build_filters(
    *,
    country_code: str | None,
    period: Literal["24h", "7d", "30d"],
    marketplace_id: UUID | None,
    category_id: UUID | None,
    direction: Literal["up", "down", "all"],
    threshold: float,
    limit: int,
    offset: int,
    sort_by: Literal["abs_change", "changed_at"],
) -> MovementsFilters:
    return MovementsFilters(
        country_code=country_code.strip().upper() if country_code else None,
        period=period,
        marketplace_id=marketplace_id,
        category_id=category_id,
        direction=direction,
        threshold=Decimal(str(threshold)),
        limit=limit,
        offset=offset,
        sort_by=sort_by,
    )


def _get_movers_sync(filters: MovementsFilters) -> MoversPage:
    """Sync bridge: read typed rows, build Pydantic model before session close."""
    db = sync_session_factory()
    try:
        rows = read_mover_rows(filters, db)
        return MovementsCalc.get_movers(filters, rows)
    finally:
        db.close()


def _get_movers_kpi_sync(filters: MovementsFilters) -> MoversKpi:
    db = sync_session_factory()
    try:
        rows = read_mover_rows(filters, db)
        return MovementsCalc.count_movers(filters, rows)
    finally:
        db.close()


def _get_movers_summary_sync(filters: MovementsFilters) -> MoversSummary:
    db = sync_session_factory()
    try:
        rows = read_mover_rows(filters, db)
        return MovementsCalc.movement_summary(filters, rows)
    finally:
        db.close()


def _get_movers_coverage_sync(filters: MovementsFilters) -> MoversCoverageMeta:
    db = sync_session_factory()
    try:
        counts = read_coverage_counts(filters, db)
        return MovementsCalc.coverage_meta(filters, counts)
    finally:
        db.close()


@router.get("/movements", response_model=MoversPage)
async def get_movers(
    _current_user: CurrentUser,
    db: DbSession,
    country_code: str | None = Query(default=None, min_length=2, max_length=2),
    period: Literal["24h", "7d", "30d"] = Query(default="24h"),
    marketplace_id: UUID | None = Query(default=None),
    category_id: UUID | None = Query(default=None),
    direction: Literal["up", "down", "all"] = Query(default="all"),
    threshold: float = Query(default=5.0, ge=0),
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    sort_by: Literal["abs_change", "changed_at"] = Query(default="abs_change"),
    display_currency: str = Query("local", description="local|EUR|USD"),
) -> MoversPage:
    """Paginated movers feed (available for a future list widget)."""
    filters = _build_filters(
        country_code=country_code,
        period=period,
        marketplace_id=marketplace_id,
        category_id=category_id,
        direction=direction,
        threshold=threshold,
        limit=limit,
        offset=offset,
        sort_by=sort_by,
    )
    normalized_display_currency = normalize_display_currency(display_currency)
    converter = await CurrencyConverter.load_latest(db)
    page = await asyncio.to_thread(_get_movers_sync, filters)
    apply_display_currency(page.items, converter, normalized_display_currency)
    return page


@router.get("/movements/kpi", response_model=MoversKpi)
async def get_movers_kpi(
    _current_user: CurrentUser,
    country_code: str | None = Query(default=None, min_length=2, max_length=2),
    period: Literal["24h", "7d", "30d"] = Query(default="24h"),
    marketplace_id: UUID | None = Query(default=None),
    category_id: UUID | None = Query(default=None),
    direction: Literal["up", "down", "all"] = Query(default="all"),
    threshold: float = Query(default=5.0, ge=0),
) -> MoversKpi:
    """Count of listings with abs(price_change_pct) above threshold."""
    filters = _build_filters(
        country_code=country_code,
        period=period,
        marketplace_id=marketplace_id,
        category_id=category_id,
        direction=direction,
        threshold=threshold,
        limit=20,
        offset=0,
        sort_by="abs_change",
    )
    return await asyncio.to_thread(_get_movers_kpi_sync, filters)


@router.get("/movements/summary", response_model=MoversSummary)
async def get_movers_summary(
    _current_user: CurrentUser,
    country_code: str | None = Query(default=None, min_length=2, max_length=2),
    period: Literal["24h", "7d", "30d"] = Query(default="24h"),
    marketplace_id: UUID | None = Query(default=None),
    category_id: UUID | None = Query(default=None),
) -> MoversSummary:
    """Movement aggregates including avg_abs_change for the overview KPI."""
    filters = _build_filters(
        country_code=country_code,
        period=period,
        marketplace_id=marketplace_id,
        category_id=category_id,
        direction="all",
        threshold=5.0,
        limit=20,
        offset=0,
        sort_by="abs_change",
    )
    return await asyncio.to_thread(_get_movers_summary_sync, filters)


@router.get("/movements/coverage", response_model=MoversCoverageMeta)
async def get_movers_coverage(
    _current_user: CurrentUser,
    country_code: str | None = Query(default=None, min_length=2, max_length=2),
    period: Literal["24h", "7d", "30d"] = Query(default="24h"),
    marketplace_id: UUID | None = Query(default=None),
    category_id: UUID | None = Query(default=None),
) -> MoversCoverageMeta:
    """Honest data-accumulation signal for thin movement history."""
    filters = _build_filters(
        country_code=country_code,
        period=period,
        marketplace_id=marketplace_id,
        category_id=category_id,
        direction="all",
        threshold=5.0,
        limit=20,
        offset=0,
        sort_by="abs_change",
    )
    return await asyncio.to_thread(_get_movers_coverage_sync, filters)
