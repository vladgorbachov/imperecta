"""List-page price harvesting tasks (SITEMAP_FIRST slice 2).

Fetch a category/list page once, extract dozens of (url, price) offers via
the Rust core, ingest them through the standard firewall path. Pattern-A
worker bridge for DB access.
"""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import Settings
from app.models.dimensions import DimMarketplace
from app.observability.sentry_init import capture_exception_if_initialized
from app.workers.celery_app import celery_app

slog = structlog.get_logger(__name__)

DEFAULT_PAGES_PER_RUN = 20

# Permanent collection (approved roadmap item 1): every beat tick harvests
# the least-recently-harvested shops that have discovered category pages.
# Rotation state is operational, not business data — it lives in a Redis
# ZSET (code -> last-run epoch), same store the worker log relay uses.
HARVEST_ROTATION_KEY = "harvest:rotation"
HARVEST_SHOPS_PER_TICK = 6
# Fallback page quota when a shop's pool size is unknown (mv not refreshed).
HARVEST_PAGES_PER_SHOP = 25

# Paginated category walk (2026-09-19). Before this the harvester refetched
# page 1 of the first N category URLs every tick — the same ~25 cards per
# category forever (pigu: 3 categories for 1.05M listings). Now a per-shop
# cursor (category index, next-page URL) walks every page of every category
# and wraps into a new pass; the quota per run is sized so each shop's whole
# pool is walked once per HARVEST_TARGET_PASS_DAYS (= the proxy provider's
# billing cycle, the period the paid budget is spread over).
HARVEST_CURSOR_KEY = "harvest:cursor:"
HARVEST_TARGET_PASS_DAYS = 30
HARVEST_TICKS_PER_DAY = 48  # beat: */30
# Offers per list page until a shop has its own measurement (EMA in the
# cursor). 30 = the mid of the 20-30 observed in the 2026-09-18 datacomp/
# techmart validation runs.
HARVEST_OFFERS_PER_PAGE_INIT = 30.0
HARVEST_PAGES_MIN = 5
HARVEST_PAGES_MAX = 300
# Loop guard, not a tuning knob: a category whose pagination never ends
# (self-linking "next") is abandoned after this many pages; at 30 offers a
# page that is 15k products — larger real categories resume on the next
# pass because the cursor moves on to the following category.
HARVEST_MAX_PAGES_PER_CATEGORY = 500

# List-page render mode per shop (harvest optimisation #2). On the paid
# backend a JS render costs 2.2x a plain fetch (Decodo $49 plan: $0.65 vs
# $0.30 per 1k). Most category pages are server-rendered for SEO, so each
# shop is probed once: the same first category page fetched without and
# with JS; no-JS wins when it yields at least as many cards (and enough to
# be a listing at all). The verdict is operational state in Redis and
# expires so a shop that changes its storefront is re-probed.
HARVEST_LIST_MODE_KEY = "harvest:listmode:"
HARVEST_LIST_MODE_TTL_SEC = 7 * 24 * 3600
LIST_MODE_NOJS = "nojs"
LIST_MODE_JS = "js"


def _run_async(coro):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    with ThreadPoolExecutor(
        max_workers=1, thread_name_prefix="harvest-async-bridge"
    ) as executor:
        return executor.submit(asyncio.run, coro).result()


def _make_session_factory() -> tuple:
    settings = Settings()
    engine = create_async_engine(
        str(settings.database_url),
        pool_size=2,
        max_overflow=0,
        pool_pre_ping=True,
        connect_args={"statement_cache_size": 0},
    )
    factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )
    return engine, factory


def _ingest_offers_sync(offers: list[dict[str, Any]], marketplace_id) -> dict[str, int]:
    """Own sync session per page (thread-safe under asyncio.to_thread)."""
    from app.database import sync_session_factory
    from app.modules.ingestion.list_offers import ingest_list_offers

    db = sync_session_factory()
    try:
        return ingest_list_offers(db, offers=offers, marketplace_id=marketplace_id)
    finally:
        db.close()


def _cursor_key(marketplace_code: str) -> str:
    return f"{HARVEST_CURSOR_KEY}{marketplace_code}"


def load_cursor(client, marketplace_code: str) -> dict:
    raw = client.hgetall(_cursor_key(marketplace_code)) or {}

    def _s(v):
        return v.decode() if isinstance(v, bytes) else v

    raw = {_s(k): _s(v) for k, v in raw.items()}
    return {
        "cat_idx": int(raw.get("cat_idx") or 0),
        "next_url": raw.get("next_url") or None,
        "page": int(raw.get("page") or 0),
        "pass_no": int(raw.get("pass_no") or 0),
        "yield_ema": float(raw.get("yield_ema") or HARVEST_OFFERS_PER_PAGE_INIT),
    }


def save_cursor(client, marketplace_code: str, cursor: dict) -> None:
    client.hset(
        _cursor_key(marketplace_code),
        mapping={
            "cat_idx": cursor["cat_idx"],
            "next_url": cursor["next_url"] or "",
            "page": cursor["page"],
            "pass_no": cursor["pass_no"],
            "yield_ema": round(cursor["yield_ema"], 2),
        },
    )


def next_page_url(html: str, current_url: str) -> str | None:
    from bs4 import BeautifulSoup

    from app.modules.scraper.extractors import detect_next_page

    try:
        return detect_next_page(BeautifulSoup(html, "html.parser"), current_url)
    except Exception:  # noqa: BLE001 - pagination is best-effort
        return None


def _list_mode_key(marketplace_code: str) -> str:
    return f"{HARVEST_LIST_MODE_KEY}{marketplace_code}"


def decide_list_mode(nojs_offers: int, js_offers: int) -> str:
    """No-JS wins only when it is a listing on its own and loses no cards."""
    from app.common.html_parsing import REPEATED_STRUCTURE_MIN_COUNT

    if nojs_offers >= REPEATED_STRUCTURE_MIN_COUNT and nojs_offers >= js_offers:
        return LIST_MODE_NOJS
    return LIST_MODE_JS


async def probe_list_mode(
    pool, core, url: str, *, requires_js: bool, scrape_tier: int
) -> tuple[str, dict]:
    """Two fetches of one category page: without JS, then with JS."""
    counts: dict[str, int] = {}
    for label, render_js in ((LIST_MODE_NOJS, False), (LIST_MODE_JS, True)):
        fetch = await pool.fetch_listing_html(
            url, requires_js=requires_js, scrape_tier=scrape_tier, render_js=render_js
        )
        if fetch.deadline_skipped:
            return LIST_MODE_JS, {"status": "budget_skip"}
        counts[label] = len(core.extract_list_offers(fetch.html, url)) if fetch.html else 0
    return decide_list_mode(counts[LIST_MODE_NOJS], counts[LIST_MODE_JS]), counts


def pages_for_shop(pool_size: int | None, eligible_shops: int, yield_ema: float) -> int:
    """Per-run page quota so the shop's pool is walked once per target pass.

    pages/day = pool / offers_per_page / HARVEST_TARGET_PASS_DAYS; a shop is
    picked every eligible/HARVEST_SHOPS_PER_TICK ticks, so each pick must
    cover that many ticks' worth. Clamped to [HARVEST_PAGES_MIN, _MAX].
    """
    if not pool_size or pool_size <= 0:
        return HARVEST_PAGES_PER_SHOP
    per_page = max(yield_ema, 1.0)
    picks_per_day = HARVEST_TICKS_PER_DAY * HARVEST_SHOPS_PER_TICK / max(eligible_shops, 1)
    pages_per_day = pool_size / per_page / HARVEST_TARGET_PASS_DAYS
    quota = pages_per_day / max(picks_per_day, 1e-9)
    return int(min(HARVEST_PAGES_MAX, max(HARVEST_PAGES_MIN, round(quota))))


async def _harvest(marketplace_code: str, limit: int) -> dict:
    try:
        import imperecta_core
    except ImportError:
        return {"status": "rust_core_unavailable", "code": marketplace_code}

    from app.modules.discovery import cursor_store
    from app.modules.discovery.fetch_adapter import fetch_params_from_marketplace
    from app.modules.scraper.pipeline.worker_log_relay import _get_redis
    from app.modules.scraper.scraper_pool import ScraperPool

    engine, factory = _make_session_factory()
    try:
        async with factory() as db:
            marketplace = (
                await db.execute(
                    select(DimMarketplace).where(
                        DimMarketplace.marketplace_code == marketplace_code
                    )
                )
            ).scalar_one_or_none()
            if marketplace is None:
                return {"status": "unknown_marketplace", "code": marketplace_code}
            category_urls = list(
                cursor_store.get_discovered_category_urls(marketplace) or []
            )
            # Registers the shop's access_mode + politeness interval for its
            # host: without this the proxy-mode shops were harvested through
            # the datacenter path (2026-09-19 audit).
            requires_js, scrape_tier = fetch_params_from_marketplace(marketplace)
    finally:
        await engine.dispose()

    if not category_urls:
        return {
            "status": "no_category_urls",
            "code": marketplace_code,
            "hint": "run discovery first or pass URLs explicitly",
        }

    redis = _get_redis()
    cursor = load_cursor(redis, marketplace_code)
    pool = ScraperPool()
    list_mode = redis.get(_list_mode_key(marketplace_code))
    list_mode = list_mode.decode() if isinstance(list_mode, bytes) else list_mode
    probe: dict = {}
    if list_mode not in (LIST_MODE_NOJS, LIST_MODE_JS):
        list_mode, probe = await probe_list_mode(
            pool,
            imperecta_core,
            category_urls[cursor["cat_idx"] % len(category_urls)],
            requires_js=requires_js,
            scrape_tier=scrape_tier,
        )
        if probe.get("status") != "budget_skip":
            redis.set(_list_mode_key(marketplace_code), list_mode, ex=HARVEST_LIST_MODE_TTL_SEC)
    render_js: bool | None = False if list_mode == LIST_MODE_NOJS else None
    pages = 0
    totals = {
        "matched": 0,
        "saved": 0,
        "unknown": 0,
        "unpriced": 0,
        "suspicious": 0,
        "onboarded": 0,
        "empty_pages": 0,
        "categories_done": 0,
    }
    marketplace_id = marketplace.id
    budget_stopped = False
    visited: set[str] = set()

    def _advance_category() -> None:
        cursor["cat_idx"] += 1
        cursor["next_url"] = None
        cursor["page"] = 0
        totals["categories_done"] += 1
        visited.clear()

    while pages < limit:
        if cursor["cat_idx"] >= len(category_urls):
            cursor["cat_idx"] = 0
            cursor["next_url"] = None
            cursor["page"] = 0
            cursor["pass_no"] += 1
            visited.clear()
        url = cursor["next_url"] or category_urls[cursor["cat_idx"]]
        fetch = await pool.fetch_listing_html(
            url, requires_js=requires_js, scrape_tier=scrape_tier, render_js=render_js
        )
        if fetch.deadline_skipped:
            # Paid budget for today is spent: stop WITHOUT moving the cursor
            # so the same page is the first one fetched next time.
            budget_stopped = True
            break
        pages += 1
        visited.add(url)
        if not fetch.html:
            totals["empty_pages"] += 1
            _advance_category()
            continue
        offers = imperecta_core.extract_list_offers(fetch.html, url)
        if not offers:
            totals["empty_pages"] += 1
            _advance_category()
            continue
        cursor["yield_ema"] = 0.8 * cursor["yield_ema"] + 0.2 * len(offers)
        counters = await asyncio.to_thread(_ingest_offers_sync, offers, marketplace_id)
        for key in ("matched", "saved", "unknown", "unpriced", "suspicious", "onboarded"):
            totals[key] += counters.get(key, 0)
        nxt = next_page_url(fetch.html, url)
        if (
            nxt
            and nxt != url
            and nxt not in visited
            and cursor["page"] + 1 < HARVEST_MAX_PAGES_PER_CATEGORY
        ):
            cursor["next_url"] = nxt
            cursor["page"] += 1
        else:
            _advance_category()

    save_cursor(redis, marketplace_code, cursor)
    return {
        "status": "budget_exhausted" if budget_stopped and pages == 0 else "completed",
        "code": marketplace_code,
        "pages_fetched": pages,
        "budget_stopped": budget_stopped,
        "cursor_category": cursor["cat_idx"],
        "cursor_page": cursor["page"],
        "pass_no": cursor["pass_no"],
        "yield_ema": round(cursor["yield_ema"], 1),
        "list_mode": list_mode,
        "list_mode_probe": probe,
        **totals,
    }


# acks_late: a deploy's SIGTERM must not eat a queued/running harvest — the
# task is idempotent (no_change dedupe + url_hash onboarding dedupe), so a
# visibility-timeout redelivery after a worker death is safe and desired.
@celery_app.task(name="harvest_list_pages", bind=True, acks_late=True)
def harvest_list_pages(
    self,
    marketplace_code: str,
    limit: int = DEFAULT_PAGES_PER_RUN,
) -> dict:
    """Harvest prices from up to `limit` known category pages of one shop."""
    try:
        summary = _run_async(_harvest(marketplace_code, limit))
        slog.info("harvest_list_pages_done", **summary)
        return summary
    except Exception as exc:
        slog.error(
            "harvest_list_pages_failed",
            marketplace_code=marketplace_code,
            error=str(exc)[:500],
        )
        capture_exception_if_initialized(exc)
        return {"status": f"error:{type(exc).__name__}", "code": marketplace_code}


def _shops_with_categories_sync() -> list[str]:
    """Active marketplace codes that have discovered category pages."""
    return [code for code, _pool in _shops_with_categories_and_pool_sync()]


def _shops_with_categories_and_pool_sync() -> list[tuple[str, int | None]]:
    """(marketplace_code, active pool size) for shops with category pages.

    Pool sizes come from mv_marketplace_stats (pg_cron, 10 min) — never a
    live count over fact_listing.
    """
    from sqlalchemy import case, text
    from sqlalchemy import func as sa_func

    from app.database import sync_session_factory

    # jsonb_array_length() raises on non-array JSON and Postgres does not
    # short-circuit AND predicates, so a single legacy '{}' row used to fail
    # the whole query for EVERY shop (2026-09-19 incident: harvest down 22h).
    # CASE guarantees evaluation order; non-array rows count as empty.
    cat_urls = DimMarketplace.discovered_category_urls
    safe_length = case(
        (sa_func.jsonb_typeof(cat_urls) == "array", sa_func.jsonb_array_length(cat_urls)),
        else_=0,
    )
    db = sync_session_factory()
    try:
        rows = db.execute(
            select(DimMarketplace.marketplace_code, DimMarketplace.id)
            .where(DimMarketplace.is_active)
            .where(safe_length > 0)
        ).all()
        codes = [(r[0], r[1]) for r in rows]
        pools: dict = {}
        if codes:
            stat_rows = db.execute(
                text(
                    "SELECT marketplace_id, listing_count FROM mv_marketplace_stats "
                    "WHERE marketplace_id = ANY(:ids)"
                ),
                {"ids": [mid for _, mid in codes]},
            ).all()
            pools = {r[0]: int(r[1]) for r in stat_rows}
        return [(code, pools.get(mid)) for code, mid in codes]
    finally:
        db.close()


def _pick_rotation_shops(codes: list[str], count: int) -> list[str]:
    """Least-recently-harvested `count` codes; missing score = never = first."""
    import time as _time

    from app.modules.scraper.pipeline.worker_log_relay import _get_redis

    client = _get_redis()
    scores = client.zmscore(HARVEST_ROTATION_KEY, codes) if codes else []
    ranked = sorted(zip(codes, scores), key=lambda cs: cs[1] or 0.0)
    picked = [code for code, _ in ranked[:count]]
    if picked:
        now = _time.time()
        client.zadd(HARVEST_ROTATION_KEY, {code: now for code in picked})
    return picked


# acks_late: idempotent — a redelivered tick just advances the rotation.
@celery_app.task(name="harvest_tick", bind=True, acks_late=True)
def harvest_tick(self) -> dict:
    """Dispatch list-page harvesting for the stalest shops (beat-driven)."""
    try:
        from app.modules.scraper.pipeline.worker_log_relay import _get_redis

        shops = _shops_with_categories_and_pool_sync()
        pool_by_code = dict(shops)
        codes = [code for code, _ in shops]
        picked = _pick_rotation_shops(codes, HARVEST_SHOPS_PER_TICK)
        redis = _get_redis()
        quotas: dict[str, int] = {}
        for code in picked:
            yield_ema = load_cursor(redis, code)["yield_ema"]
            quotas[code] = pages_for_shop(pool_by_code.get(code), len(codes), yield_ema)
            harvest_list_pages.apply_async([code], kwargs={"limit": quotas[code]})
        summary = {
            "status": "completed",
            "eligible": len(codes),
            "dispatched": picked,
            "quotas": quotas,
        }
        slog.info("harvest_tick_done", **summary)
        return summary
    except Exception as exc:
        capture_exception_if_initialized(exc)
        slog.error("harvest_tick_failed", error=str(exc)[:500])
        return {"status": f"error:{type(exc).__name__}"}
