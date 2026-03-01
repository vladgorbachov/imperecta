"""Digest generation Celery tasks."""

import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_maker
from app.models import Digest, PriceSnapshot, Product, User
from app.models.user import UserPlan
from app.services.ai_service import generate_digest as ai_generate_digest
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def _run_async(coro):
    """Run async coroutine from sync Celery task."""
    import asyncio

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


async def _collect_period_data(
    session: AsyncSession,
    user_id: UUID,
    period_start: datetime,
    period_end: datetime,
) -> dict:
    """Collect price changes, new promos, out-of-stock for period."""
    from app.models import CompetitorProduct

    price_changes = []
    new_promos = []
    out_of_stock = []

    cps_result = await session.execute(
        select(CompetitorProduct, Product.name)
        .join(Product, CompetitorProduct.product_id == Product.id)
        .where(Product.user_id == user_id)
    )
    rows = cps_result.all()

    for cp, product_name in rows:
        snapshots_result = await session.execute(
            select(PriceSnapshot)
            .where(
                PriceSnapshot.competitor_product_id == cp.id,
                PriceSnapshot.scraped_at >= period_start,
                PriceSnapshot.scraped_at <= period_end,
            )
            .order_by(PriceSnapshot.scraped_at.asc())
        )
        snapshots = snapshots_result.scalars().all()

        for i, snap in enumerate(snapshots):
            if i > 0 and snap.old_price and snap.old_price > 0 and snap.price != snap.old_price:
                change_pct = float((snap.old_price - snap.price) / snap.old_price * 100)
                item = {
                    "product_name": product_name,
                    "change": f"{snap.old_price} → {snap.price} ({change_pct:+.1f}%)",
                    "change_percent": change_pct,
                }
                price_changes.append(item)
            if snap.promo_label:
                new_promos.append({
                    "product_name": product_name,
                    "promo_label": snap.promo_label,
                })
            if not snap.in_stock:
                out_of_stock.append({"product_name": product_name})

    anomalies = [c for c in price_changes if abs(c.get("change_percent", 0)) > 15]
    return {
        "top_changes": price_changes[:20],
        "promos": new_promos[:20],
        "anomalies": anomalies[:10],
        "summary_stats": {
            "total_changes": len(price_changes),
            "total_promos": len(new_promos),
            "out_of_stock_count": len(out_of_stock),
        },
    }


@celery_app.task
def generate_weekly_digest(user_id: str) -> None:
    """Collect week data, generate digest via AI, save to DB, send via email/Telegram."""

    async def _do():
        async with async_session_maker() as session:
            user_result = await session.execute(
                select(User).where(User.id == UUID(user_id))
            )
            user = user_result.scalar_one_or_none()
            if not user:
                return

            now = datetime.now(timezone.utc)
            period_end = now
            period_start = now - timedelta(days=7)

            data = await _collect_period_data(session, user.id, period_start, period_end)
            content_md = await ai_generate_digest(user.id, data)

            digest = Digest(
                user_id=user.id,
                period_type="weekly",
                period_start=period_start,
                period_end=period_end,
                content_md=content_md,
            )
            session.add(digest)
            await session.flush()

            _send_digest(user, content_md, "weekly")
            digest.sent_at = now
            await session.commit()
            logger.info("Weekly digest generated for user_id=%s", user_id)

    _run_async(_do())


@celery_app.task
def generate_daily_digest(user_id: str) -> None:
    """Daily digest. Only for users with plan != starter."""

    async def _do():
        async with async_session_maker() as session:
            user_result = await session.execute(
                select(User).where(User.id == UUID(user_id))
            )
            user = user_result.scalar_one_or_none()
            if not user or user.plan == UserPlan.starter:
                return

            now = datetime.now(timezone.utc)
            period_end = now
            period_start = now - timedelta(days=1)

            data = await _collect_period_data(session, user.id, period_start, period_end)
            content_md = await ai_generate_digest(user.id, data)

            digest = Digest(
                user_id=user.id,
                period_type="daily",
                period_start=period_start,
                period_end=period_end,
                content_md=content_md,
            )
            session.add(digest)
            await session.flush()

            _send_digest(user, content_md, "daily")
            digest.sent_at = now
            await session.commit()
            logger.info("Daily digest generated for user_id=%s", user_id)

    _run_async(_do())


@celery_app.task
def schedule_weekly_digests() -> None:
    """Enqueue generate_weekly_digest for all users."""

    async def _do():
        async with async_session_maker() as session:
            result = await session.execute(select(User.id))
            for row in result.all():
                generate_weekly_digest.delay(str(row[0]))

    _run_async(_do())


@celery_app.task
def schedule_daily_digests() -> None:
    """Enqueue generate_daily_digest for users with plan != starter."""

    async def _do():
        async with async_session_maker() as session:
            result = await session.execute(
                select(User.id).where(User.plan != UserPlan.starter)
            )
            for row in result.all():
                generate_daily_digest.delay(str(row[0]))

    _run_async(_do())


def _send_digest(user: "User", content_md: str, period: str) -> None:
    """Send digest via email and/or Telegram based on user preferences."""
    try:
        from app.notifications.email_sender import send_digest_email_to_user
        from app.notifications.telegram_bot import send_digest_telegram

        subject = f"Imperecta: {period.capitalize()} digest"
        send_digest_email_to_user(user.id, subject, content_md)
        if user.telegram_chat_id:
            send_digest_telegram(user.id, content_md)
    except Exception as e:
        logger.warning("Digest send failed: %s", e)
