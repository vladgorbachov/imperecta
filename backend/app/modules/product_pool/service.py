"""Global product pool: listings joined to dim_product and dim_marketplace."""

import base64
import json
from datetime import date, datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    MetaData,
    Numeric,
    Table,
    and_,
    asc,
    desc,
    func,
    nullsfirst,
    nullslast,
    or_,
    select,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models.dimensions import DimBrand, DimCategory, DimDate, DimMarketplace, DimProduct
from app.models.facts import FactListing, FactPrice
from app.modules.currency import (
    DISPLAY_LOCAL,
    CurrencyConverter,
    compute_display_fields_for_marketplace,
)

_SORT_RECENT = "recent"
_SORT_NAME_ASC = "name_asc"
_SORT_NAME_DESC = "name_desc"
_SORT_PRICE_ASC = "price_asc"
_SORT_PRICE_DESC = "price_desc"
_SORT_TRENDING = "trending"
_SORT_GAINERS = "gainers"
_SORT_LOSERS = "losers"
_SORT_VOLATILE = "volatile"
SPARKLINE_POINTS_LIMIT = 14

# P12: exact counts are capped — beyond this the total is an estimate.
COUNT_CAP = 10_000

# P12 search: matched-product prefilter cap. An inline ILIKE inside the
# ordered list query lets the planner walk the sort index filtering names
# per row — unbounded for rare terms (observed 30s+). Resolving matching
# product ids first (trgm bitmap, strictly capped) bounds the work.
SEARCH_MATCH_CAP = 5_000

# Second phase cap: candidate LISTINGS fetched by product_id (bitmap, no
# ordering) before the bounded top-N sort. Without this the planner may
# still walk a sort index testing ANY(5000 ids) per row — observed 125s
# timeout live. Two bounded phases give a deterministic plan.
SEARCH_LISTING_CAP = 10_000


def _keyset_columns(sort: str):
    """(column, direction) for sorts that support keyset pagination.

    Sorts ordered by a computed price-change (gainers/losers/volatile) keep
    offset pagination: their key lives in a per-request subquery.
    """
    mapping = {
        _SORT_RECENT: (FactListing.last_checked_at, "desc"),
        _SORT_TRENDING: (FactListing.last_checked_at, "desc"),
        _SORT_NAME_ASC: (DimProduct.name, "asc"),
        _SORT_NAME_DESC: (DimProduct.name, "desc"),
        _SORT_PRICE_ASC: (FactListing.last_price, "asc"),
        _SORT_PRICE_DESC: (FactListing.last_price, "desc"),
    }
    return mapping.get(sort)


def _encode_cursor(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, separators=(",", ":"), default=str)
    return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")


def _decode_cursor(cursor: str) -> dict[str, Any] | None:
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded.encode()).decode())
    except (ValueError, UnicodeDecodeError):
        return None
    if not isinstance(payload, dict) or "id" not in payload:
        return None
    return payload


def _cursor_sort_value(sort: str, row_value: Any) -> Any:
    """Serialize a row's sort key into the cursor (None survives as None)."""
    if row_value is None:
        return None
    if isinstance(row_value, datetime):
        return row_value.isoformat()
    return str(row_value) if not isinstance(row_value, str) else row_value


def _parse_cursor_value(sort: str, value: Any) -> Any:
    if value is None:
        return None
    if sort in (_SORT_RECENT, _SORT_TRENDING):
        return datetime.fromisoformat(value)
    if sort in (_SORT_PRICE_ASC, _SORT_PRICE_DESC):
        return float(value)
    return value


def _keyset_where(column, direction: str, value: Any, last_id, *, backwards: bool):
    """Predicate selecting rows strictly after (or before) (value, id).

    Ordering contract: ASC/DESC with NULLS LAST, id ASC as the tiebreaker.
    """
    if not backwards:
        if value is None:
            return and_(column.is_(None), FactListing.id > last_id)
        ahead = column < value if direction == "desc" else column > value
        return or_(
            ahead,
            and_(column == value, FactListing.id > last_id),
            column.is_(None),
        )
    if value is None:
        # Before a NULL row: every non-null row, plus earlier NULL rows.
        return or_(column.isnot(None), and_(column.is_(None), FactListing.id < last_id))
    behind = column > value if direction == "desc" else column < value
    return or_(behind, and_(column == value, FactListing.id < last_id))

_POOL_STATS_STMT = text(
    """
    SELECT total_products, total_listings, marketplaces_count,
           listings_with_price, last_updated
    FROM mv_pool_stats
    """
)

# Lightweight Core reflection of the materialized view (migration 066): the
# MV is not an ORM entity and must not join the model metadata.
_MV_MARKETPLACE_STATS = Table(
    "mv_marketplace_stats",
    MetaData(),
    Column("marketplace_id", PG_UUID(as_uuid=True), primary_key=True),
    Column("listing_count", BigInteger),
    Column("avg_price_eur", Numeric),
    Column("refreshed_at", DateTime(timezone=True)),
)


def _pool_product_visibility_filter():
    """Listings that are gated products or legacy rows with a scraped price."""
    return or_(
        FactListing.page_role == "product",
        and_(FactListing.page_role.is_(None), FactListing.last_price.isnot(None)),
    )


_BROWSE_SET_KEY = "pool:browse:"
_browse_redis: Any | None = None


def _get_browse_redis() -> Any:
    global _browse_redis
    if _browse_redis is None:
        import redis.asyncio as redis_async

        _browse_redis = redis_async.from_url(Settings().redis_url, decode_responses=True)
    return _browse_redis


async def _browse_cache_get(key: str) -> list[UUID] | None:
    try:
        raw = await _get_browse_redis().get(key)
    except Exception:  # noqa: BLE001 - cache miss on any Redis trouble
        return None
    if not raw:
        return None
    try:
        return [UUID(v) for v in json.loads(raw)]
    except (ValueError, TypeError):
        return None


async def _browse_cache_put(key: str, ids: list[UUID], ttl_sec: int) -> None:
    try:
        await _get_browse_redis().set(key, json.dumps([str(i) for i in ids]), ex=ttl_sec)
    except Exception:  # noqa: BLE001 - the next request recomputes
        return


def cap_per_source(
    rows: list[tuple[Any, Any]], per_source: int, depth: int
) -> list[Any]:
    """Keep the ordered prefix of `rows` = (listing_id, marketplace_id) with
    at most `per_source` rows per marketplace, `depth` rows in total.

    One pass, O(n) with a per-marketplace counter — the re-utilisation cap
    of counsel §3.9 (Innoweb / CV-Online): unfiltered browsing never shows a
    substantial part of any single source. Pure so both the Python and the
    Rust read path (data_ops::pool_products) share the test vectors.
    """
    seen: dict[Any, int] = {}
    kept: list[Any] = []
    for listing_id, marketplace_id in rows:
        n = seen.get(marketplace_id, 0)
        if n >= per_source:
            continue
        seen[marketplace_id] = n + 1
        kept.append(listing_id)
        if len(kept) >= depth:
            break
    return kept


class ProductPoolService:
    """List and aggregate global pool rows from v2 star schema.

    price_change_pct reads the denormalized fact_listing.last_price_change_pct
    (migration 057) — O(1) per row. The previous implementation windowed ALL
    of fact_price into every list/detail/export query: O(price history) per
    request, a scaling cliff the load rule forbids.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    def _base_listing_stmt(self):
        """Shared SELECT for pool listings with optional price-change join."""
        return (
            select(
                FactListing.id,
                DimProduct.id.label("product_id"),
                DimMarketplace.id.label("marketplace_id"),
                DimProduct.name.label("title"),
                DimProduct.image_url,
                FactListing.external_url.label("url"),
                DimMarketplace.name.label("marketplace_name"),
                DimMarketplace.domain.label("marketplace_domain"),
                DimMarketplace.marketplace_code,
                DimMarketplace.country_code,
                FactListing.last_price.label("price"),
                FactListing.last_currency_code.label("currency"),
                FactListing.last_price_eur.label("price_eur"),
                FactListing.last_checked_at,
                FactListing.is_active,
                FactListing.last_price_change_pct.label("price_change_pct"),
                # P10: taxonomy labels on the list grain (detail shares them).
                DimBrand.name.label("brand"),
                DimCategory.name.label("category"),
                # P13: type + universal-language layer (null until enriched).
                DimProduct.product_type,
                DimProduct.product_type_en,
                DimProduct.title_en,
                DimCategory.name_en.label("category_en"),
            )
            .select_from(FactListing)
            .join(DimProduct, FactListing.product_id == DimProduct.id)
            .join(DimMarketplace, FactListing.marketplace_id == DimMarketplace.id)
            .outerjoin(DimBrand, DimProduct.brand_id == DimBrand.id)
            .outerjoin(DimCategory, DimProduct.category_id == DimCategory.id)
            # Bare column, not .is_(True): "IS TRUE" defeats partial-index matching.
            .where(FactListing.is_active)
            .where(_pool_product_visibility_filter())
        )

    def _apply_filters(
        self,
        stmt,
        *,
        search: str | None,
        marketplace_id: UUID | None,
        category: str | None,
        country_code: str | None = None,
    ):
        if search:
            like = f"%{search}%"
            stmt = stmt.where(DimProduct.name.ilike(like))
        if marketplace_id is not None:
            stmt = stmt.where(FactListing.marketplace_id == marketplace_id)
        if country_code:
            stmt = stmt.where(
                DimMarketplace.country_code == country_code.strip().upper(),
            )
        if category:
            cat = f"%{category}%"
            stmt = stmt.where(
                or_(
                    DimMarketplace.domain.ilike(cat),
                    DimMarketplace.name.ilike(cat),
                    DimMarketplace.marketplace_code.ilike(cat),
                )
            )
        return stmt

    def _apply_sort(self, stmt, sort: str):
        """Apply ordering for pool list; id ASC tiebreaker matches the
        (sort key, id) order indexes of migrations 056/057."""
        pct = FactListing.last_price_change_pct
        tiebreak = asc(FactListing.id)
        if sort == _SORT_NAME_ASC:
            return stmt.order_by(asc(DimProduct.name), tiebreak)
        if sort == _SORT_NAME_DESC:
            return stmt.order_by(desc(DimProduct.name), tiebreak)
        if sort == _SORT_PRICE_ASC:
            return stmt.order_by(nullslast(asc(FactListing.last_price)), tiebreak)
        if sort == _SORT_PRICE_DESC:
            return stmt.order_by(nullslast(desc(FactListing.last_price)), tiebreak)
        if sort == _SORT_GAINERS:
            return stmt.order_by(nullslast(desc(pct)), tiebreak)
        if sort == _SORT_LOSERS:
            return stmt.order_by(nullslast(asc(pct)), tiebreak)
        if sort in (_SORT_VOLATILE, "volatile"):
            return stmt.order_by(nullslast(desc(func.abs(pct))), tiebreak)
        if sort in (_SORT_TRENDING, "trending"):
            return stmt.order_by(nullslast(desc(FactListing.last_checked_at)), tiebreak)
        # recent and unknown
        return stmt.order_by(nullslast(desc(FactListing.last_checked_at)), tiebreak)

    async def list_products(
        self,
        *,
        sort: str = "recent",
        search: str | None = None,
        marketplace_id: UUID | None = None,
        category: str | None = None,
        country_code: str | None = None,
        limit: int = 20,
        offset: int = 0,
        cursor: str | None = None,
        skip_total: bool = False,
        display_currency: str = DISPLAY_LOCAL,
    ) -> tuple[list[dict[str, Any]], int | None, dict[str, Any]]:
        """List pool rows; returns (items, total, page_meta).

        page_meta: total_is_estimate, next_cursor, prev_cursor. P12: a valid
        `cursor` replaces offset for keyset-capable sorts; computed-pct sorts
        (gainers/losers/volatile) silently keep offset (next_cursor stays
        None, the frontend keeps its offset pager for them). skip_total=True
        skips the count query entirely and returns total=None — the alert
        dialog's typeahead (limit=6) ignores totals.
        """
        search_listing_ids: list | None = None
        search_capped = False
        if search:
            search_ids, ids_capped = await self._search_product_ids(search)
            if not search_ids:
                return [], 0, {
                    "total_is_estimate": False,
                    "next_cursor": None,
                    "prev_cursor": None,
                }
            # Phase 2: candidate listings by product_id — bitmap, unordered,
            # capped. The final query then filters on ≤SEARCH_LISTING_CAP
            # primary keys: bounded top-N sort, deterministic plan.
            search_listing_ids, listings_capped = await self._search_listing_ids(
                search_ids
            )
            if not search_listing_ids:
                return [], 0, {
                    "total_is_estimate": False,
                    "next_cursor": None,
                    "prev_cursor": None,
                }
            search_capped = ids_capped or listings_capped

        unfiltered = (
            search_listing_ids is None
            and marketplace_id is None
            and not category
            and not country_code
        )
        if unfiltered:
            return await self._browse_page(
                sort=sort,
                limit=limit,
                offset=offset,
                display_currency=display_currency,
                skip_total=skip_total,
            )

        stmt = self._base_listing_stmt()
        stmt = self._apply_filters(
            stmt,
            search=None,
            marketplace_id=marketplace_id,
            category=category,
            country_code=country_code,
        )
        if search_listing_ids is not None:
            stmt = stmt.where(FactListing.id.in_(search_listing_ids))

        keyset = _keyset_columns(sort)
        cursor_payload = _decode_cursor(cursor) if (cursor and keyset) else None
        backwards = bool(cursor_payload and cursor_payload.get("d") == "prev")
        if keyset is not None:
            column, direction = keyset
            if cursor_payload is not None:
                stmt = stmt.where(
                    _keyset_where(
                        column,
                        direction,
                        _parse_cursor_value(sort, cursor_payload.get("v")),
                        cursor_payload["id"],
                        backwards=backwards,
                    )
                )
            order = desc(column) if direction == "desc" else asc(column)
            if backwards:
                # Walk the ordering in reverse; rows are re-reversed below.
                rev = asc(column) if direction == "desc" else desc(column)
                stmt = stmt.order_by(nullsfirst(rev), desc(FactListing.id))
            else:
                stmt = stmt.order_by(nullslast(order), asc(FactListing.id))
            stmt = stmt.limit(limit)
            if cursor_payload is None:
                stmt = stmt.offset(offset)
        else:
            stmt = self._apply_sort(stmt, sort)
            stmt = stmt.limit(limit).offset(offset)

        total: int | None
        if skip_total:
            total, total_is_estimate = None, False
        else:
            total, total_is_estimate = await self._count_pool(
                search_listing_ids=search_listing_ids,
                marketplace_id=marketplace_id,
                category=category,
                country_code=country_code,
            )
            total_is_estimate = total_is_estimate or search_capped
        result = await self.db.execute(stmt)
        rows = result.mappings().all()
        if backwards:
            rows = list(reversed(rows))
        items = [_row_to_pool_item(dict(r)) for r in rows]
        listing_ids = [item["id"] for item in items]
        recent_prices_by_listing = await self._get_recent_prices_map(listing_ids)
        for item in items:
            item["recent_prices"] = recent_prices_by_listing.get(item["id"], [])
        await self._apply_display_currency(items, display_currency)

        next_cursor = prev_cursor = None
        if keyset is not None and rows:
            raw_first, raw_last = dict(rows[0]), dict(rows[-1])
            key = "last_checked_at" if sort in (_SORT_RECENT, _SORT_TRENDING) else (
                "title" if sort in (_SORT_NAME_ASC, _SORT_NAME_DESC) else "price"
            )
            full_page = len(rows) == limit
            # First page forward has nothing before it; otherwise both edges
            # get cursors (an empty neighbour page just returns no rows).
            if full_page or backwards:
                next_cursor = _encode_cursor({
                    "d": "next",
                    "v": _cursor_sort_value(sort, raw_last.get(key)),
                    "id": str(raw_last["id"]),
                })
            if cursor_payload is not None or offset > 0:
                prev_cursor = _encode_cursor({
                    "d": "prev",
                    "v": _cursor_sort_value(sort, raw_first.get(key)),
                    "id": str(raw_first["id"]),
                })
        page_meta = {
            "total_is_estimate": total_is_estimate,
            "next_cursor": next_cursor,
            "prev_cursor": prev_cursor,
        }
        return items, (int(total) if total is not None else None), page_meta

    async def _browse_page(
        self,
        *,
        sort: str,
        limit: int,
        offset: int,
        display_currency: str,
        skip_total: bool = False,
    ) -> tuple[list[dict[str, Any]], int | None, dict[str, Any]]:
        """Unfiltered browsing (WP2): a shared, per-sort browse set instead of
        the raw pool order.

        The set = the first `pool_browse_scan_cap` rows of the sort order
        (narrow, index-driven scan of ids only), capped to
        `pool_max_per_source_unfiltered` per marketplace and
        `page_size_max * page_depth_max` rows in total; it is identical for
        every viewer, so it is computed once per sort and shared through
        Redis for `pool_browse_cache_sec`. Pages are slices of it, hydrated
        by primary key — offset pagination only (no cursors past the depth).
        """
        settings = Settings()
        depth = settings.pool_page_size_max * settings.pool_page_depth_max
        browse_ids = await self._browse_set(sort, settings=settings, depth=depth)
        page_ids = browse_ids[offset : offset + limit]
        items: list[dict[str, Any]] = []
        if page_ids:
            stmt = self._base_listing_stmt().where(FactListing.id.in_(page_ids))
            rows = {r["id"]: dict(r) for r in (await self.db.execute(stmt)).mappings()}
            items = [_row_to_pool_item(rows[i]) for i in page_ids if i in rows]
            recent = await self._get_recent_prices_map([i["id"] for i in items])
            for item in items:
                item["recent_prices"] = recent.get(item["id"], [])
            await self._apply_display_currency(items, display_currency)
        return items, (None if skip_total else len(browse_ids)), {
            "total_is_estimate": False,
            "next_cursor": None,
            "prev_cursor": None,
        }

    async def _browse_set(self, sort: str, *, settings: Settings, depth: int) -> list[UUID]:
        cache_key = f"{_BROWSE_SET_KEY}{sort}"
        cached = await _browse_cache_get(cache_key)
        if cached is not None:
            return cached
        narrow = (
            select(FactListing.id, FactListing.marketplace_id)
            .select_from(FactListing)
            .where(FactListing.is_active)
            .where(_pool_product_visibility_filter())
        )
        if sort in (_SORT_NAME_ASC, _SORT_NAME_DESC):
            narrow = narrow.join(DimProduct, FactListing.product_id == DimProduct.id)
        narrow = self._apply_sort(narrow, sort).limit(settings.pool_browse_scan_cap)
        scanned = (await self.db.execute(narrow)).all()
        browse_ids = cap_per_source(
            [(r[0], r[1]) for r in scanned], settings.pool_max_per_source_unfiltered, depth
        )
        await _browse_cache_put(cache_key, browse_ids, settings.pool_browse_cache_sec)
        return browse_ids

    async def _search_product_ids(self, search: str) -> tuple[list, bool]:
        """Matching dim_product ids via the trgm index, capped (P12)."""
        like = f"%{search}%"
        rows = await self.db.execute(
            select(DimProduct.id)
            .where(DimProduct.name.ilike(like))
            .limit(SEARCH_MATCH_CAP)
        )
        ids = [r[0] for r in rows]
        return ids, len(ids) == SEARCH_MATCH_CAP

    async def _search_listing_ids(self, product_ids: list) -> tuple[list, bool]:
        """Candidate listing ids for matched products — bitmap scan, capped."""
        rows = await self.db.execute(
            select(FactListing.id)
            .where(FactListing.product_id.in_(product_ids))
            .where(FactListing.is_active)
            .limit(SEARCH_LISTING_CAP)
        )
        ids = [r[0] for r in rows]
        return ids, len(ids) == SEARCH_LISTING_CAP

    async def _count_pool(
        self,
        *,
        search_listing_ids: list | None,
        marketplace_id: UUID | None,
        category: str | None,
        country_code: str | None,
    ) -> tuple[int, bool]:
        """P12: pool totals without a 1.4M-row count(*) per request.

        Unfiltered → mv_pool_stats (pg_cron keeps it fresh; estimate=True).
        Filtered → exact count capped at COUNT_CAP+1 rows; beyond the cap the
        total is COUNT_CAP and flagged as an estimate.
        """
        unfiltered = (
            search_listing_ids is None
            and marketplace_id is None
            and category is None
            and country_code is None
        )
        if unfiltered:
            row = (await self.db.execute(_POOL_STATS_STMT)).mappings().first()
            if row is not None:
                return int(row["total_listings"] or 0), True

        inner = (
            select(FactListing.id)
            .select_from(FactListing)
            .join(DimProduct, FactListing.product_id == DimProduct.id)
            .join(DimMarketplace, FactListing.marketplace_id == DimMarketplace.id)
            .where(FactListing.is_active)
            .where(_pool_product_visibility_filter())
        )
        inner = self._apply_filters(
            inner,
            search=None,
            marketplace_id=marketplace_id,
            category=category,
            country_code=country_code,
        )
        if search_listing_ids is not None:
            inner = inner.where(FactListing.id.in_(search_listing_ids))
        capped = inner.limit(COUNT_CAP + 1).subquery()
        counted = await self.db.scalar(select(func.count()).select_from(capped)) or 0
        if counted > COUNT_CAP:
            return COUNT_CAP, True
        return int(counted), False


    async def get_product_detail(
        self,
        listing_id: UUID,
        *,
        display_currency: str = DISPLAY_LOCAL,
    ) -> dict[str, Any] | None:
        """One PoolProductItem by listing id + taxonomy labels; None when hidden.

        Same visibility rules as the list (active gated product + blocked-country
        filter), so a hidden/blocked listing is indistinguishable from absent.
        """
        stmt = self._base_listing_stmt().where(FactListing.id == listing_id)
        stmt = stmt.add_columns(DimProduct.attributes.label("attributes"))
        row = (await self.db.execute(stmt)).mappings().first()
        if row is None:
            return None
        raw = dict(row)
        attributes = raw.pop("attributes", None)
        item = _row_to_pool_item(raw)
        prices_map = await self._get_recent_prices_map([item["id"]])
        item["recent_prices"] = prices_map.get(item["id"], [])
        await self._apply_display_currency([item], display_currency)
        item["attributes"] = attributes if isinstance(attributes, dict) and attributes else None
        item["description"] = (
            attributes.get("description") if isinstance(attributes, dict) else None
        )
        return item

    async def get_price_history(
        self,
        listing_id: UUID,
        *,
        period: str = "30d",
    ) -> dict[str, Any] | None:
        """Daily price series for one listing; None when the listing is hidden.

        Latest scrape per day wins (same dedupe as visualisation_calc/trend);
        native price and price_eur both returned; data_ready needs >=2 days.
        """
        visible = await self.get_product_detail(
            listing_id,
        )
        if visible is None:
            return None

        days = {"7d": 7, "30d": 30, "90d": 90}.get(period, 30)
        today = datetime.now(timezone.utc).date()
        start = today - timedelta(days=days)
        min_date_id = start.year * 10_000 + start.month * 100 + start.day
        max_date_id = today.year * 10_000 + today.month * 100 + today.day

        ranked = (
            select(
                FactPrice.date_id,
                FactPrice.price,
                FactPrice.price_eur,
                FactPrice.currency_code,
                func.row_number()
                .over(
                    partition_by=[FactPrice.date_id],
                    order_by=desc(FactPrice.scraped_at),
                )
                .label("rn"),
            )
            .where(
                FactPrice.listing_id == listing_id,
                FactPrice.date_id >= min_date_id,
                FactPrice.date_id <= max_date_id,
            )
        ).subquery("ranked_prices")
        stmt = (
            select(ranked.c.date_id, ranked.c.price, ranked.c.price_eur, ranked.c.currency_code)
            .where(ranked.c.rn == 1)
            .order_by(ranked.c.date_id)
        )
        rows = (await self.db.execute(stmt)).all()
        points = [
            {
                "date": date(r.date_id // 10_000, r.date_id // 100 % 100, r.date_id % 100),
                "price": float(r.price) if r.price is not None else None,
                "price_eur": float(r.price_eur) if r.price_eur is not None else None,
            }
            for r in rows
        ]
        return {
            "listing_id": listing_id,
            "currency": visible.get("currency"),
            "period": period,
            "points": points if len(points) >= 2 else [],
            "data_ready": len(points) >= 2,
        }

    async def _apply_display_currency(
        self,
        items: list[dict[str, Any]],
        display_currency: str,
    ) -> None:
        """Populate display_price / display_currency / conversion_available /
        local_currency_resolution on items.

        For ``local`` mode the marketplace's local currency is resolved from
        the domain TLD (or country_code fallback); the parsed currency is
        converted into it when they differ. For ``EUR``/``USD`` the previous
        behaviour applies, plus the resolution metadata is still surfaced so
        the UI can disable the local-currency toggle when undeterminable.
        """
        if not items:
            return
        converter = await CurrencyConverter.load_latest(self.db)
        for item in items:
            fields = compute_display_fields_for_marketplace(
                amount=item.get("price"),
                currency=item.get("currency"),
                display_currency=display_currency,
                converter=converter,
                marketplace_domain=item.get("marketplace_domain"),
                marketplace_country_code=item.get("country_code"),
            )
            item.update(fields)

    async def _get_recent_prices_map(
        self,
        listing_ids: list[UUID],
        *,
        points_limit: int = SPARKLINE_POINTS_LIMIT,
    ) -> dict[UUID, list[dict[str, Any]]]:
        """Load recent price points for listings in one query."""
        if not listing_ids:
            return {}

        ranked = (
            select(
                FactPrice.listing_id.label("listing_id"),
                DimDate.full_date.label("full_date"),
                FactPrice.price.label("price"),
                FactPrice.currency_code.label("currency_code"),
                func.row_number().over(
                    partition_by=FactPrice.listing_id,
                    order_by=desc(FactPrice.date_id),
                ).label("row_num"),
            )
            .select_from(FactPrice)
            .join(DimDate, DimDate.date_id == FactPrice.date_id)
            .where(FactPrice.listing_id.in_(listing_ids))
        ).subquery()

        stmt = (
            select(
                ranked.c.listing_id,
                ranked.c.full_date,
                ranked.c.price,
                ranked.c.currency_code,
            )
            .where(ranked.c.row_num <= points_limit)
            .order_by(ranked.c.listing_id, ranked.c.full_date)
        )
        result = await self.db.execute(stmt)
        rows = result.all()

        output: dict[UUID, list[dict[str, Any]]] = {}
        for row in rows:
            output.setdefault(row.listing_id, []).append({
                "date": row.full_date.isoformat(),
                "price": float(row.price),
                "currency": row.currency_code,
            })
        return output

    async def get_categories(self) -> list[dict]:
        """Distinct marketplaces that have active listings (lightweight category browse).

        Served from mv_marketplace_stats (066): the live GROUP BY over
        3M fact_listing rows took 6-10s per Products-page load.
        """
        stmt = (
            select(
                DimMarketplace.id,
                DimMarketplace.marketplace_code,
                DimMarketplace.name,
                DimMarketplace.domain,
                DimMarketplace.country_code,
                _MV_MARKETPLACE_STATS.c.listing_count.label("listing_count"),
            )
            .select_from(_MV_MARKETPLACE_STATS)
            .join(DimMarketplace, _MV_MARKETPLACE_STATS.c.marketplace_id == DimMarketplace.id)
            .where(_MV_MARKETPLACE_STATS.c.listing_count > 0)
            .order_by(desc("listing_count"))
        )
        result = await self.db.execute(stmt)
        return [
            {
                "marketplace_id": str(r.id),
                "marketplace_code": r.marketplace_code,
                "name": r.name,
                "domain": r.domain,
                "country_code": r.country_code,
                "listing_count": int(r.listing_count),
            }
            for r in result.all()
        ]

    async def get_marketplace_stats(self) -> list[dict]:
        """Per-marketplace listing counts and average price (EUR) when available.

        Reads mv_marketplace_stats (pg_cron, every 10 min — migration 066)
        instead of aggregating all of fact_listing per request, which hit
        statement_timeout on the shared instance.
        """
        listing_count = func.coalesce(_MV_MARKETPLACE_STATS.c.listing_count, 0).label(
            "listing_count"
        )
        stmt = (
            select(
                DimMarketplace.id.label("marketplace_id"),
                DimMarketplace.name.label("marketplace_name"),
                DimMarketplace.domain.label("marketplace_domain"),
                DimMarketplace.country_code,
                listing_count,
                _MV_MARKETPLACE_STATS.c.avg_price_eur.label("avg_price_eur"),
            )
            .select_from(DimMarketplace)
            .outerjoin(
                _MV_MARKETPLACE_STATS,
                _MV_MARKETPLACE_STATS.c.marketplace_id == DimMarketplace.id,
            )
            .where(DimMarketplace.is_active.is_(True))
            .order_by(desc("listing_count"), asc(DimMarketplace.name))
        )
        result = await self.db.execute(stmt)
        out: list[dict] = []
        for r in result.all():
            avg = r.avg_price_eur
            out.append({
                "marketplace_domain": r.marketplace_domain,
                "marketplace_name": r.marketplace_name,
                "country_code": r.country_code,
                "product_count": int(r.listing_count),
                "avg_price": float(avg) if avg is not None else None,
            })
        return out

    async def get_pool_stats(self) -> dict:
        """Aggregate counts for the global pool dashboard card.

        Reads the single-row mv_pool_stats (refreshed by pg_cron every 10
        minutes, migration 051) instead of counting the 1.4M+ fact_listing
        rows per request — the live counts were hitting statement_timeout.
        """
        row = (await self.db.execute(_POOL_STATS_STMT)).mappings().first()
        if row is None:
            return {
                "total_products": 0,
                "total_listings": 0,
                "marketplaces_count": 0,
                "listings_with_price": 0,
                "last_updated": None,
            }
        return {
            "total_products": int(row["total_products"] or 0),
            "total_listings": int(row["total_listings"] or 0),
            "marketplaces_count": int(row["marketplaces_count"] or 0),
            "listings_with_price": int(row["listings_with_price"] or 0),
            "last_updated": row["last_updated"],
        }


def _row_to_pool_item(row: dict[str, Any]) -> dict[str, Any]:
    """Normalize ORM row mapping to API dict (UUIDs as str for JSON).

    Returns canonical-only fields. PP1 removed the legacy duplicate names
    (current_price, last_scraped_at, price_change_pct_24h) and the always-None
    placeholders (original_price, price_change_pct_7d/30d, volatility_30d):
    canonical readers are `price`, `last_checked_at`, `price_change_pct`.
    display_* / conversion_available / local_currency_* are populated later by
    `_apply_display_currency`; we seed them here so consumers can rely on the
    keys existing even when display currency resolution is skipped.
    """
    pct = row.get("price_change_pct")
    return {
        "id": row["id"],
        "marketplace_id": row.get("marketplace_id"),
        "product_id": row["product_id"],
        "title": row.get("title"),
        "image_url": row.get("image_url"),
        "url": row.get("url"),
        # Source attribution (counsel §3.9): the origin listing and its host
        # on every card; `url`/`marketplace_domain` stay until WP8 retires them.
        "external_url": row.get("url"),
        "source_domain": row.get("marketplace_domain"),
        "marketplace_name": row.get("marketplace_name"),
        "marketplace_domain": row.get("marketplace_domain"),
        "marketplace_code": row.get("marketplace_code"),
        "country_code": row.get("country_code"),
        "brand": row.get("brand"),
        "category": row.get("category"),
        "product_type": row.get("product_type"),
        "product_type_en": row.get("product_type_en"),
        "category_en": row.get("category_en"),
        "title_en": row.get("title_en"),
        "price": float(row["price"]) if row.get("price") is not None else None,
        "currency": row.get("currency"),
        "price_eur": float(row["price_eur"]) if row.get("price_eur") is not None else None,
        "price_change_pct": float(pct) if pct is not None else None,
        "display_price": None,
        "display_currency": None,
        "conversion_available": False,
        "local_currency_resolution": None,
        "local_currency_unavailable": False,
        "last_checked_at": row.get("last_checked_at"),
        "status": "active" if row.get("is_active") else "inactive",
        "is_active": row.get("is_active"),
        "recent_prices": [],
    }
