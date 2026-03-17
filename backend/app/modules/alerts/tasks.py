"""Alert evaluation Celery tasks."""

import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.database import async_session_maker
from app.models import Competitor, CompetitorProduct, Product
from app.modules.alerts.models import Alert, AlertEvent
from app.modules.alerts.notifications import (
    send_alert_email_to_user,
    send_out_of_stock_alert,
    send_price_alert,
    send_promo_alert,
)
from app.modules.alerts.service import generate_alert_explanation
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)
DEBOUNCE_MINUTES = 60


def _run_async(coro):
    import asyncio

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _parse_decimal(s: str | None) -> Decimal | None:
    if s is None or s == "":
        return None
    try:
        return Decimal(s)
    except Exception:
        return None


@celery_app.task
def check_alerts(competitor_product_id: str, old_price: str | None, new_price: str, promo_label: str, old_in_stock: str | None = None, new_in_stock: str | None = None) -> None:
    async def _do():
        async with async_session_maker() as session:
            row = (
                await session.execute(
                    select(CompetitorProduct, Product, Competitor)
                    .join(Product, CompetitorProduct.product_id == Product.id)
                    .join(Competitor, CompetitorProduct.competitor_id == Competitor.id)
                    .where(CompetitorProduct.id == UUID(competitor_product_id))
                )
            ).one_or_none()
            if not row:
                return
            cp, product, competitor = row
            alerts = (
                await session.execute(
                    select(Alert).options(joinedload(Alert.user)).where(Alert.is_active.is_(True), (Alert.product_id.is_(None)) | (Alert.product_id == product.id))
                )
            ).scalars().all()
            new_price_dec = _parse_decimal(new_price)
            old_price_dec = _parse_decimal(old_price)
            old_stock = old_in_stock == "true" if old_in_stock else None
            new_stock = new_in_stock == "true" if new_in_stock else None
            cutoff = datetime.now(timezone.utc) - timedelta(minutes=DEBOUNCE_MINUTES)

            for alert in alerts:
                if (
                    await session.execute(
                        select(AlertEvent.id).where(
                            AlertEvent.alert_id == alert.id,
                            AlertEvent.competitor_product_id == cp.id,
                            AlertEvent.triggered_at >= cutoff,
                        )
                    )
                ).scalar_one_or_none():
                    continue

                triggered = False
                message = ""
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
                    event = AlertEvent(
                        alert_id=alert.id,
                        competitor_product_id=cp.id,
                        old_price=old_price_dec,
                        new_price=new_price_dec,
                        message=message,
                        sent_via=alert.channel,
                        severity=severity,
                    )
                    session.add(event)
                    await session.flush()
                    if severity in ("critical", "warning"):
                        generate_alert_ai_explanation.apply_async(args=[event.id], countdown=3)
                    await _send_notification(
                        alert=alert,
                        message=message,
                        channel=alert.channel,
                        product_name=product.name,
                        competitor_name=competitor.name,
                        marketplace=competitor.marketplace or "",
                        old_price=float(old_price_dec) if old_price_dec else 0,
                        new_price=float(new_price_dec) if new_price_dec else 0,
                        promo_label=promo_label or "",
                    )
            await session.commit()

    _run_async(_do())


@celery_app.task(name="generate_alert_ai_explanation")
def generate_alert_ai_explanation(alert_event_id: int) -> None:
    async def _do():
        async with async_session_maker() as session:
            try:
                await generate_alert_explanation(session, alert_event_id)
                await session.commit()
            except Exception as error:
                logger.warning("generate_alert_explanation failed for event %s: %s", alert_event_id, error)

    _run_async(_do())


async def _send_notification(alert: Alert, message: str, channel: str, product_name: str, competitor_name: str, marketplace: str, old_price: float, new_price: float, promo_label: str) -> None:
    if channel in ("email", "both"):
        send_alert_email_to_user(alert.user_id, message)
    if channel in ("telegram", "both"):
        chat_id = alert.user.telegram_chat_id if alert.user else None
        if not chat_id:
            return
        if alert.type in ("price_drop", "price_increase"):
            await send_price_alert(chat_id, product_name, competitor_name, old_price, new_price, "RUB", marketplace)
        elif alert.type == "out_of_stock":
            await send_out_of_stock_alert(chat_id, product_name, competitor_name, marketplace)
        elif alert.type == "new_promo":
            await send_promo_alert(chat_id, product_name, competitor_name, promo_label, marketplace)
