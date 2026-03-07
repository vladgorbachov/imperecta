"""Scraping Celery tasks."""

import asyncio
import logging
import random
import time
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_maker
from app.models import AdminMarketplace, Competitor, CompetitorProduct, Product, User
from app.scrapers.engine import ScraperFactory
from app.services.price_service import scrape_competitor_product
from app.workers.alert_tasks import check_alerts
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def _run_async(coro):
    """Run async coroutine from sync Celery task."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


async def _log_scrape_and_update_admin(
    session: AsyncSession,
    marketplace_id: str,
    marketplace_name: str,
    url: str,
    competitor_product_id: UUID,
    status: str,
    error_message: str | None = None,
    price_found=None,
    duration_ms: int | None = None,
    proxy_used: bool = False,
) -> None:
    """Log scrape to scrape_logs and update admin_marketplaces if applicable."""
    scraper = ScraperFactory.create("generic")
    await scraper._log_scrape(
        session,
        marketplace_id=marketplace_id,
        marketplace_name=marketplace_name,
        url=url,
        status=status,
        error_message=error_message,
        price_found=float(price_found) if price_found is not None else None,
        duration_ms=duration_ms,
        proxy_used=proxy_used,
        competitor_product_id=competitor_product_id,
    )

    result = await session.execute(
        select(AdminMarketplace).where(AdminMarketplace.marketplace_id == marketplace_id)
    )
    am = result.scalar_one_or_none()
    if am:
        from datetime import datetime, timezone

        am.last_scrape_at = datetime.now(timezone.utc)
        am.last_scrape_status = status
        am.last_error = error_message
        am.total_scrapes += 1
        if status == "success":
            am.successful_scrapes += 1
        else:
            am.failed_scrapes += 1


@celery_app.task(bind=True, max_retries=3)
def scrape_single(self, competitor_product_id: str) -> None:
    """Scrape single competitor product, save snapshot, trigger alert check."""

    async def _do():
        async with async_session_maker() as session:
            result = await session.execute(
                select(CompetitorProduct, Competitor)
                .join(Competitor, CompetitorProduct.competitor_id == Competitor.id)
                .where(CompetitorProduct.id == UUID(competitor_product_id))
            )
            row = result.one_or_none()
            if not row:
                raise ValueError("Competitor product not found")
            cp, competitor = row
            old_price = str(cp.last_price) if cp.last_price is not None else None
            old_in_stock = cp.last_in_stock

            marketplace_id = competitor.marketplace
            marketplace_name = competitor.name or marketplace_id

            start = time.time()
            try:
                data = await scrape_competitor_product(
                    UUID(competitor_product_id), session
                )
                duration_ms = int((time.time() - start) * 1000)
                await _log_scrape_and_update_admin(
                    session,
                    marketplace_id=marketplace_id,
                    marketplace_name=marketplace_name,
                    url=cp.url,
                    competitor_product_id=cp.id,
                    status="success",
                    price_found=data.price,
                    duration_ms=duration_ms,
                )
                await session.commit()
                check_alerts.delay(
                    competitor_product_id,
                    old_price,
                    str(data.price),
                    data.promo_label or "",
                    str(old_in_stock).lower() if old_in_stock is not None else None,
                    str(data.in_stock).lower(),
                )
                logger.info(
                    "Scraped cp_id=%s price=%s",
                    competitor_product_id,
                    data.price,
                )
            except Exception as exc:
                duration_ms = int((time.time() - start) * 1000)
                status_str = "timeout" if "timeout" in str(exc).lower() else "error"
                await _log_scrape_and_update_admin(
                    session,
                    marketplace_id=marketplace_id,
                    marketplace_name=marketplace_name,
                    url=cp.url,
                    competitor_product_id=cp.id,
                    status=status_str,
                    error_message=str(exc),
                    duration_ms=duration_ms,
                )
                await session.rollback()
                raise

    try:
        _run_async(_do())
    except Exception as exc:
        logger.warning("Scrape failed cp_id=%s: %s", competitor_product_id, exc)
        raise self.retry(exc=exc)


@celery_app.task
def scrape_user_products(user_id: str) -> None:
    """Get all active competitor_products for user, enqueue scrape_single with stagger."""

    async def _get_ids():
        async with async_session_maker() as session:
            result = await session.execute(
                select(CompetitorProduct.id)
                .join(Product, CompetitorProduct.product_id == Product.id)
                .where(
                    Product.user_id == UUID(user_id),
                    CompetitorProduct.is_active.is_(True),
                )
            )
            return [str(row[0]) for row in result.all()]

    ids = _run_async(_get_ids())
    for i, cp_id in enumerate(ids):
        delay = random.uniform(2, 5) * i
        scrape_single.apply_async(args=[cp_id], countdown=delay)


@celery_app.task
def scrape_all() -> None:
    """Get all users, enqueue scrape_user_products for each."""

    async def _get_user_ids():
        async with async_session_maker() as session:
            result = await session.execute(select(User.id))
            return [str(row[0]) for row in result.all()]

    user_ids = _run_async(_get_user_ids())
    for uid in user_ids:
        scrape_user_products.delay(uid)


