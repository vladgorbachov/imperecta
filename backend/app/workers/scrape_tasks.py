"""Scraping Celery tasks."""

import asyncio
import logging
import random
import time
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import joinedload

from app.database import sync_session_factory
from app.models import AdminMarketplace, CompetitorProduct, PriceSnapshot, ScrapeLog
from app.scrapers.engine import ScrapeResult
from app.services.price_service import _detect_scraper_type, _get_scraper
from app.workers.alert_tasks import check_alerts
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def _update_admin_marketplace(db, marketplace_id: str, status: str, error_message: str | None) -> None:
    """Update AdminMarketplace stats if exists."""
    am = db.query(AdminMarketplace).filter(AdminMarketplace.marketplace_id == marketplace_id).first()
    if am:
        am.last_scrape_at = datetime.now(timezone.utc)
        am.last_scrape_status = status
        am.last_error = error_message
        am.total_scrapes += 1
        if status == "success":
            am.successful_scrapes += 1
        else:
            am.failed_scrapes += 1


@celery_app.task(
    name="scrape_single",
    bind=True,
    max_retries=2,
    default_retry_delay=30,
    soft_time_limit=60,
    time_limit=90,
)
def scrape_single(self, competitor_product_id: str):
    """
    Scrape a single competitor product URL.
    Pipeline: fetch page -> extract price -> save to price_snapshots -> update competitor_product -> log.
    """
    start_time = time.time()

    with sync_session_factory() as db:
        cp = (
            db.query(CompetitorProduct)
            .options(joinedload(CompetitorProduct.competitor))
            .filter(
                CompetitorProduct.id == UUID(competitor_product_id),
                CompetitorProduct.is_active.is_(True),
            )
            .first()
        )

        if not cp:
            logger.warning("CompetitorProduct %s not found or inactive", competitor_product_id)
            return {"status": "skipped", "reason": "not found"}

        competitor = cp.competitor
        marketplace_id = competitor.marketplace if competitor else "unknown"
        marketplace_name = competitor.name if competitor else marketplace_id

        scraper_type = _detect_scraper_type(cp.url, cp.scraper_type)
        try:
            scraper = _get_scraper(scraper_type, cp.css_selector_price)
        except Exception as e:
            logger.error("Failed to create scraper for type '%s': %s", scraper_type, e)
            duration_ms = int((time.time() - start_time) * 1000)
            db.add(
                ScrapeLog(
                    marketplace_id=marketplace_id,
                    marketplace_name=marketplace_name,
                    competitor_product_id=cp.id,
                    url=cp.url,
                    status="error",
                    error_message=f"Scraper creation failed: {e}",
                    duration_ms=duration_ms,
                )
            )
            _update_admin_marketplace(db, marketplace_id, "error", str(e))
            db.commit()
            return {"status": "error", "error": str(e)}

        try:
            result: ScrapeResult = asyncio.run(scraper.scrape(cp.url))
            duration_ms = int((time.time() - start_time) * 1000)
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error("Scrape failed for %s: %s", cp.url[:80], e)

            error_str = str(e).lower()
            if "timeout" in error_str:
                status = "timeout"
            elif "403" in error_str or "blocked" in error_str or "captcha" in error_str:
                status = "blocked"
            else:
                status = "error"

            db.add(
                ScrapeLog(
                    marketplace_id=marketplace_id,
                    marketplace_name=marketplace_name,
                    competitor_product_id=cp.id,
                    url=cp.url,
                    status=status,
                    error_message=str(e)[:2000],
                    duration_ms=duration_ms,
                    proxy_used=getattr(scraper.proxy_manager, "is_available", False),
                )
            )
            _update_admin_marketplace(db, marketplace_id, status, str(e))
            db.commit()

            if status == "timeout" and self.request.retries < self.max_retries:
                raise self.retry(exc=e)
            return {"status": status, "error": str(e)}

        if result and result.price is not None and result.price > 0:
            old_price = cp.last_price
            old_in_stock = cp.last_in_stock

            snapshot = PriceSnapshot(
                competitor_product_id=cp.id,
                price=result.price,
                old_price=result.old_price,
                promo_label=result.promo_label,
                in_stock=result.in_stock if result.in_stock is not None else True,
            )
            db.add(snapshot)

            cp.last_price = result.price
            cp.last_promo_label = result.promo_label
            cp.last_in_stock = result.in_stock if result.in_stock is not None else True
            cp.last_checked_at = datetime.now(timezone.utc)
            if result.product_name and not cp.name:
                cp.name = result.product_name[:500]

            db.add(
                ScrapeLog(
                    marketplace_id=marketplace_id,
                    marketplace_name=marketplace_name,
                    competitor_product_id=cp.id,
                    url=cp.url,
                    status="success",
                    price_found=result.price,
                    duration_ms=duration_ms,
                    proxy_used=getattr(scraper.proxy_manager, "is_available", False),
                )
            )
            _update_admin_marketplace(db, marketplace_id, "success", None)
            db.commit()

            logger.info(
                "Scraped %s: price=%s (was %s)",
                cp.url[:80],
                result.price,
                old_price,
            )

            # Fire-and-forget: check alerts on every success (handles price_drop, price_increase, out_of_stock, new_promo)
            check_alerts.delay(
                competitor_product_id,
                str(old_price) if old_price is not None else None,
                str(result.price),
                result.promo_label or "",
                str(old_in_stock).lower() if old_in_stock is not None else None,
                str(result.in_stock).lower() if result.in_stock is not None else None,
            )

            return {"status": "success", "price": float(result.price), "url": cp.url}

        duration_ms = int((time.time() - start_time) * 1000)
        db.add(
            ScrapeLog(
                marketplace_id=marketplace_id,
                marketplace_name=marketplace_name,
                competitor_product_id=cp.id,
                url=cp.url,
                status="error",
                error_message="Price not found or zero",
                duration_ms=duration_ms,
            )
        )
        _update_admin_marketplace(db, marketplace_id, "error", "Price not found or zero")
        db.commit()
        logger.warning("No price found for %s", cp.url[:80])
        return {"status": "error", "error": "Price not found"}


@celery_app.task
def scrape_user_products(user_id: str) -> None:
    """Get all active competitor_products for user, enqueue scrape_single with stagger."""

    with sync_session_factory() as db:
        from app.models import Product

        rows = (
            db.query(CompetitorProduct.id)
            .join(Product, CompetitorProduct.product_id == Product.id)
            .filter(
                Product.user_id == UUID(user_id),
                CompetitorProduct.is_active.is_(True),
            )
            .all()
        )
        ids = [str(row[0]) for row in rows]

    for i, cp_id in enumerate(ids):
        delay = random.uniform(2, 5) * i
        scrape_single.apply_async(args=[cp_id], countdown=delay)


@celery_app.task(name="scrape_all")
def scrape_all() -> None:
    """Scrape ALL active competitor_products across ALL users."""

    with sync_session_factory() as db:
        active_cps = (
            db.query(CompetitorProduct.id)
            .filter(CompetitorProduct.is_active.is_(True))
            .all()
        )

    logger.info("Queuing scrape for %d competitor_products", len(active_cps))

    for (cp_id,) in active_cps:
        scrape_single.delay(str(cp_id))

    return {"queued": len(active_cps)}
