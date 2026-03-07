"""Alert evaluation Celery tasks."""

import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.database import async_session_maker
from app.models import Alert, AlertEvent, Competitor, CompetitorProduct, Product
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
                select(CompetitorProduct, Product, Competitor)
                .join(Product, CompetitorProduct.product_id == Product.id)
                .join(Competitor, CompetitorProduct.competitor_id == Competitor.id)
                .where(CompetitorProduct.id == UUID(competitor_product_id))
            )
            row = cp_result.one_or_none()
            if not row:
                return
            cp, product, competitor = row

            alerts_result = await session.execute(
                select(Alert)
                .options(joinedload(Alert.user))
                .where(
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
                    severity = None
                    if alert.type in ("price_drop", "price_increase") and old_price_dec and new_price_dec:
                        change_pct = abs(
                            float((new_price_dec - old_price_dec) / old_price_dec * 100)
                        )
                        if change_pct > 25:
                            severity = "critical"
                        elif change_pct >= 15:
                            severity = "warning"
                        elif change_pct >= 10:
                            severity = "info"

                    event = AlertEvent(
                        alert_id=alert.id,
                        competitor_product_id=cp.id,
                        old_price=old_price_dec,
                        new_price=new_price_dec,
                        message=message,
                        sent_via=sent_via,
                        severity=severity,
                    )
                    session.add(event)
                    await session.flush()

                    # Fire-and-forget AI explanation for critical and warning only
                    if severity in ("critical", "warning"):
                        generate_alert_ai_explanation.apply_async(
                            args=[event.id],
                            countdown=3,
                        )

                    await _send_notification(
                        alert=alert,
                        message=message,
                        channel=sent_via,
                        product_name=product.name,
                        competitor_name=competitor.name,
                        marketplace=competitor.marketplace or "",
                        old_price=float(old_price_dec) if old_price_dec else 0,
                        new_price=float(new_price_dec) if new_price_dec else 0,
                        promo_label=promo_label or "",
                    )
                    logger.info("Alert triggered alert_id=%s: %s", alert.id, message)

            await session.commit()

    _run_async(_do())


@celery_app.task(name="generate_alert_ai_explanation")
def generate_alert_ai_explanation(alert_event_id: int) -> None:
    """Generate AI explanation for alert event. Fire-and-forget from check_alerts."""
    async def _do():
        async with async_session_maker() as session:
            try:
                from app.services.alert_ai_service import generate_alert_explanation

                await generate_alert_explanation(session, alert_event_id)
                await session.commit()
            except Exception as e:
                logger.warning(
                    "generate_alert_explanation failed for event %s: %s",
                    alert_event_id,
                    e,
                )

    _run_async(_do())


async def _send_notification(
    alert: Alert,
    message: str,
    channel: str,
    product_name: str,
    competitor_name: str,
    marketplace: str,
    old_price: float,
    new_price: float,
    promo_label: str,
) -> None:
    """Send notification via email and/or Telegram."""
    try:
        if channel in ("email", "both"):
            from app.notifications.email_sender import send_alert_email_to_user

            send_alert_email_to_user(alert.user_id, message)
        if channel in ("telegram", "both"):
            user = alert.user
            chat_id = user.telegram_chat_id if user else None
            if not chat_id:
                logger.warning("Alert user has no telegram_chat_id, skipping Telegram")
                return
            from app.notifications.telegram_bot import (
                send_out_of_stock_alert,
                send_price_alert,
                send_promo_alert,
            )

            if alert.type in ("price_drop", "price_increase"):
                await send_price_alert(
                    chat_id=chat_id,
                    product_name=product_name,
                    competitor_name=competitor_name,
                    old_price=old_price,
                    new_price=new_price,
                    currency="RUB",
                    marketplace=marketplace,
                )
            elif alert.type == "out_of_stock":
                await send_out_of_stock_alert(
                    chat_id=chat_id,
                    product_name=product_name,
                    competitor_name=competitor_name,
                    marketplace=marketplace,
                )
            elif alert.type == "new_promo":
                await send_promo_alert(
                    chat_id=chat_id,
                    product_name=product_name,
                    competitor_name=competitor_name,
                    promo_label=promo_label,
                    marketplace=marketplace,
                )
    except Exception as e:
        logger.warning("Notification send failed: %s", e)
