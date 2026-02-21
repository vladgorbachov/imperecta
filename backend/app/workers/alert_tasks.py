"""Alert evaluation Celery tasks."""

import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from app.database import async_session_maker
from app.models import Alert, AlertEvent, CompetitorProduct, Product
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)
DEBOUNCE_MINUTES = 60


def _run_async(coro):
    """Run async coroutine from sync Celery task."""
    import asyncio

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _parse_decimal(s: str | None) -> Decimal | None:
    """Parse decimal from string."""
    if s is None or s == "":
        return None
    try:
        return Decimal(s)
    except Exception:
        return None


@celery_app.task
def check_alerts(
    competitor_product_id: str,
    old_price: str | None,
    new_price: str,
    promo_label: str,
    old_in_stock: str | None = None,
    new_in_stock: str | None = None,
) -> None:
    """
    Check active alerts for product. Create AlertEvent and send notification if threshold exceeded.
    Debounce: skip if AlertEvent for this alert+competitor_product was < 1 hour ago.
    """

    async def _do():
        async with async_session_maker() as session:
            cp_result = await session.execute(
                select(CompetitorProduct, Product)
                .join(Product, CompetitorProduct.product_id == Product.id)
                .where(CompetitorProduct.id == UUID(competitor_product_id))
            )
            row = cp_result.one_or_none()
            if not row:
                return
            cp, product = row

            alerts_result = await session.execute(
                select(Alert).where(
                    Alert.is_active.is_(True),
                    (Alert.product_id.is_(None)) | (Alert.product_id == product.id),
                )
            )
            alerts = alerts_result.scalars().all()

            new_price_dec = _parse_decimal(new_price)
            old_price_dec = _parse_decimal(old_price)
            old_stock = old_in_stock == "true" if old_in_stock else None
            new_stock = new_in_stock == "true" if new_in_stock else None

            cutoff = datetime.now(timezone.utc) - timedelta(minutes=DEBOUNCE_MINUTES)

            for alert in alerts:
                debounce_result = await session.execute(
                    select(AlertEvent.id).where(
                        AlertEvent.alert_id == alert.id,
                        AlertEvent.competitor_product_id == cp.id,
                        AlertEvent.triggered_at >= cutoff,
                    )
                )
                if debounce_result.scalar_one_or_none():
                    continue

                triggered = False
                message = ""
                sent_via = alert.channel

                if alert.type == "price_drop" and old_price_dec and new_price_dec and alert.threshold_percent:
                    drop_pct = float((old_price_dec - new_price_dec) / old_price_dec * 100)
                    if drop_pct >= float(alert.threshold_percent):
                        triggered = True
                        message = f"Цена снизилась на {drop_pct:.1f}%: {old_price_dec} → {new_price_dec}"

                elif alert.type == "price_increase" and old_price_dec and new_price_dec and alert.threshold_percent:
                    inc_pct = float((new_price_dec - old_price_dec) / old_price_dec * 100)
                    if inc_pct >= float(alert.threshold_percent):
                        triggered = True
                        message = f"Цена выросла на {inc_pct:.1f}%: {old_price_dec} → {new_price_dec}"

                elif alert.type == "out_of_stock" and old_stock is True and new_stock is False:
                    triggered = True
                    message = "Товар закончился в наличии"

                elif alert.type == "new_promo" and promo_label:
                    triggered = True
                    message = f"Новая акция: {promo_label}"

                if triggered and message:
                    event = AlertEvent(
                        alert_id=alert.id,
                        competitor_product_id=cp.id,
                        old_price=old_price_dec,
                        new_price=new_price_dec,
                        message=message,
                        sent_via=sent_via,
                    )
                    session.add(event)
                    await session.flush()
                    _send_notification(alert, message, sent_via)
                    logger.info("Alert triggered alert_id=%s: %s", alert.id, message)

            await session.commit()

    _run_async(_do())


def _send_notification(alert: Alert, message: str, channel: str) -> None:
    """Send notification via email and/or Telegram."""
    try:
        if channel in ("email", "both"):
            from app.notifications.email_sender import send_alert_email_to_user

            send_alert_email_to_user(alert.user_id, message)
        if channel in ("telegram", "both"):
            from app.notifications.telegram_bot import send_alert_telegram

            send_alert_telegram(alert.user_id, message)
    except Exception as e:
        logger.warning("Notification send failed: %s", e)
