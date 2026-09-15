"""Alert trigger engine: evaluate active rules against fresh price facts.

Periodic worker slice (Celery beat -> evaluate_alert_rules). Reads are
operational ORM SELECTs; every write goes through the ALERT door:

* ``event_create``  -> append to alert_events (the /alerts/events feed)
* ``rule_trigger``  -> bump alerts.last_triggered_at / trigger_count

Trigger semantics (v1, listing-bound rules only):

* price_drop / price_rise — fires on the LATEST fact_price row scraped after
  the rule's watermark (max(created_at, last_triggered_at)) whose
  price_change_pct crosses threshold_pct in the rule's direction. The pct is
  the ingest-computed delta vs the listing's prior price.
* availability — fires on an is_active transition of the listing versus the
  state recorded by the rule's most recent availability event (a rule with
  no events assumes "available", so a dead listing alerts immediately).

Cooldown gates the whole rule; delivery (email/telegram/webhook) is
fail-soft: the event is recorded either way, sent_via/delivered_at only on
confirmed delivery.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.app_tables import Alert, AlertEvent
from app.models.core import User
from app.models.dimensions import DimProduct
from app.models.facts import FactListing, FactPrice
from app.modules.alerts.notifications import (
    EmailChannel,
    NotificationChannel,
    NotificationMessage,
    TelegramChannel,
    WebhookChannel,
)
from app.modules.persist.alerts_write import (
    build_alert_event_fields,
    build_alert_rule_fields,
    write_alert_async,
)

logger = logging.getLogger(__name__)

ENGINE_ALERT_TYPES = frozenset({"price_drop", "price_rise", "availability"})
_TWO_PLACES = Decimal("0.01")

_CHANNELS: dict[str, NotificationChannel] = {
    "email": EmailChannel(),
    "telegram": TelegramChannel(),
    "webhook": WebhookChannel(),
}


@dataclass(frozen=True, slots=True)
class TriggerDecision:
    """Outcome of evaluating one rule against current facts."""

    fire: bool
    old_value: float | None = None
    new_value: float | None = None
    change_pct: float | None = None
    severity: str = "medium"
    fact_price_id: int | None = None
    message: str = ""


def _in_cooldown(rule: Alert, now: datetime) -> bool:
    if rule.last_triggered_at is None:
        return False
    return now < rule.last_triggered_at + timedelta(minutes=int(rule.cooldown_minutes or 0))


def _price_watermark(rule: Alert) -> datetime:
    if rule.last_triggered_at is not None and rule.last_triggered_at > rule.created_at:
        return rule.last_triggered_at
    return rule.created_at


def _old_price_from_change(new_price: Decimal, change_pct: Decimal) -> Decimal | None:
    denominator = Decimal(1) + change_pct / Decimal(100)
    if denominator == 0:
        return None
    return (new_price / denominator).quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)


def decide_price_trigger(
    *,
    alert_type: str,
    threshold_pct: float,
    price: Decimal,
    price_change_pct: Decimal | None,
    fact_price_id: int | None,
    product_title: str,
    currency: str | None,
) -> TriggerDecision:
    """Pure decision for price_drop / price_rise against one fact_price row."""
    if price_change_pct is None:
        return TriggerDecision(fire=False)
    pct = Decimal(str(price_change_pct))
    threshold = Decimal(str(threshold_pct))
    if alert_type == "price_drop" and not pct <= -threshold:
        return TriggerDecision(fire=False)
    if alert_type == "price_rise" and not pct >= threshold:
        return TriggerDecision(fire=False)

    old_price = _old_price_from_change(Decimal(str(price)), pct)
    severity = "high" if abs(pct) >= threshold * 2 else "medium"
    direction = "dropped" if pct < 0 else "rose"
    unit = f" {currency}" if currency else ""
    old_text = f"{old_price}{unit} -> " if old_price is not None else ""
    message = (
        f"{product_title}: price {direction} {abs(pct):.1f}% "
        f"({old_text}{Decimal(str(price)).quantize(_TWO_PLACES)}{unit})"
    )
    return TriggerDecision(
        fire=True,
        old_value=float(old_price) if old_price is not None else None,
        new_value=float(price),
        change_pct=float(pct),
        severity=severity,
        fact_price_id=fact_price_id,
        message=message,
    )


def decide_availability_trigger(
    *,
    listing_is_active: bool,
    previous_state_active: bool,
    product_title: str,
) -> TriggerDecision:
    """Pure decision for availability: fires on an is_active transition."""
    if listing_is_active == previous_state_active:
        return TriggerDecision(fire=False)
    if listing_is_active:
        return TriggerDecision(
            fire=True,
            old_value=0.0,
            new_value=1.0,
            severity="medium",
            message=f"{product_title}: listing is available again",
        )
    return TriggerDecision(
        fire=True,
        old_value=1.0,
        new_value=0.0,
        severity="high",
        message=f"{product_title}: listing became unavailable",
    )


async def _latest_price_row(
    db: AsyncSession, listing_id, watermark: datetime
) -> FactPrice | None:
    result = await db.execute(
        select(FactPrice)
        .where(FactPrice.listing_id == listing_id, FactPrice.scraped_at > watermark)
        .order_by(FactPrice.scraped_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _previous_availability_state(db: AsyncSession, rule_id) -> bool:
    result = await db.execute(
        select(AlertEvent.new_value)
        .where(AlertEvent.alert_id == rule_id)
        .order_by(AlertEvent.triggered_at.desc())
        .limit(1)
    )
    last_event_value = result.scalar_one_or_none()
    if last_event_value is None:
        return True
    return float(last_event_value) >= 1.0


def _recipient_for(rule: Alert, user: User) -> str | None:
    channel = rule.channel or "email"
    if channel == "email":
        return user.email
    if channel == "telegram":
        return str(user.telegram_chat_id) if user.telegram_chat_id is not None else None
    if channel == "webhook":
        return rule.webhook_url
    return None


async def _deliver(rule: Alert, user: User, decision: TriggerDecision) -> bool:
    channel_name = rule.channel or "email"
    channel = _CHANNELS.get(channel_name)
    recipient = _recipient_for(rule, user)
    if channel is None or not recipient:
        return False
    message = NotificationMessage(
        body=decision.message,
        title="Imperecta price alert",
        data={
            "rule_id": str(rule.id),
            "listing_id": str(rule.listing_id) if rule.listing_id else None,
            "alert_type": rule.alert_type,
            "old_value": decision.old_value,
            "new_value": decision.new_value,
            "change_pct": decision.change_pct,
            "severity": decision.severity,
        },
    )
    try:
        return await channel.send(recipient, message)
    except Exception as exc:
        logger.warning("Alert delivery failed for rule %s: %s", rule.id, exc)
        return False


async def _persist_firing(
    rule: Alert, decision: TriggerDecision, now: datetime, delivered: bool
) -> bool:
    event_fields = build_alert_event_fields(
        alert_id=rule.id,
        alert_class="analytic",
        listing_id=rule.listing_id,
        fact_price_id=decision.fact_price_id,
        old_value=decision.old_value,
        new_value=decision.new_value,
        change_pct=decision.change_pct,
        message=decision.message,
        severity=decision.severity,
        sent_via=(rule.channel or "email") if delivered else None,
        delivered_at=now if delivered else None,
        triggered_at=now,
    )
    event_result = await write_alert_async(
        kind="event_create",
        fields=event_fields,
        reject_source="alerts_trigger_engine",
    )
    if not event_result.ok:
        logger.error("alert_events insert rejected for rule %s", rule.id)
        return False
    trigger_result = await write_alert_async(
        kind="rule_trigger",
        fields=build_alert_rule_fields(
            id=rule.id,
            last_triggered_at=now,
            trigger_count=int(rule.trigger_count or 0) + 1,
        ),
        reject_source="alerts_trigger_engine",
    )
    if not trigger_result.ok:
        logger.error("rule_trigger update rejected for rule %s", rule.id)
    return True


async def evaluate_alert_rules(db: AsyncSession) -> dict[str, int]:
    """Evaluate every active listing-bound rule; fire, deliver, persist.

    Returns a summary: rules considered / fired / delivered / skipped.
    """
    now = datetime.now(UTC)
    result = await db.execute(
        select(Alert, FactListing, User, DimProduct.name)
        .join(FactListing, Alert.listing_id == FactListing.id)
        .join(User, Alert.user_id == User.id)
        .outerjoin(DimProduct, Alert.product_id == DimProduct.id)
        .where(
            Alert.is_active.is_(True),
            Alert.alert_class == "analytic",
            Alert.alert_type.in_(sorted(ENGINE_ALERT_TYPES)),
        )
    )
    rows = result.all()

    considered = len(rows)
    fired = delivered_count = cooldown_skips = 0

    for rule, listing, user, product_name in rows:
        if _in_cooldown(rule, now):
            cooldown_skips += 1
            continue
        title = product_name or listing.external_name or "Tracked listing"

        if rule.alert_type == "availability":
            decision = decide_availability_trigger(
                listing_is_active=bool(listing.is_active),
                previous_state_active=await _previous_availability_state(db, rule.id),
                product_title=title,
            )
        else:
            if rule.threshold_pct is None:
                continue
            price_row = await _latest_price_row(db, rule.listing_id, _price_watermark(rule))
            if price_row is None:
                continue
            decision = decide_price_trigger(
                alert_type=rule.alert_type,
                threshold_pct=float(rule.threshold_pct),
                price=price_row.price,
                price_change_pct=price_row.price_change_pct,
                fact_price_id=price_row.id,
                product_title=title,
                currency=price_row.currency_code,
            )

        if not decision.fire:
            continue
        delivered = await _deliver(rule, user, decision)
        if await _persist_firing(rule, decision, now, delivered):
            fired += 1
            if delivered:
                delivered_count += 1

    return {
        "considered": considered,
        "fired": fired,
        "delivered": delivered_count,
        "cooldown_skips": cooldown_skips,
    }
