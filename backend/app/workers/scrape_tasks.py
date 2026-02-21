"""Scraping Celery tasks."""

import asyncio
import logging
import random
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_maker
from app.models import CompetitorProduct, Product, User
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


@celery_app.task(bind=True, max_retries=3)
def scrape_single(self, competitor_product_id: str) -> None:
    """Scrape single competitor product, save snapshot, trigger alert check."""

    async def _do():
        async with async_session_maker() as session:
            result = await session.execute(
                select(CompetitorProduct.last_price, CompetitorProduct.last_in_stock)
                .where(CompetitorProduct.id == UUID(competitor_product_id))
            )
            row = result.one_or_none()
            old_price = str(row[0]) if row and row[0] is not None else None
            old_in_stock = row[1] if row else None

            try:
                data = await scrape_competitor_product(
                    UUID(competitor_product_id), session
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
            except Exception:
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


@celery_app.task
def cleanup_old_snapshots() -> None:
    """Delete price snapshots older than 90 days."""

    async def _do():
        from datetime import datetime, timedelta, timezone

        from sqlalchemy import delete

        from app.models import PriceSnapshot

        cutoff = datetime.now(timezone.utc) - timedelta(days=90)
        async with async_session_maker() as session:
            await session.execute(delete(PriceSnapshot).where(PriceSnapshot.scraped_at < cutoff))
            await session.commit()
        logger.info("Cleaned up snapshots older than 90 days")

    _run_async(_do())
