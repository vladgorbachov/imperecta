"""Alert evaluation Celery tasks (v2: Alert / AlertEvent + FactListing / FactPrice)."""

import logging

from app.models.app_tables import Alert, AlertEvent
from app.models.facts import FactListing, FactPrice
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

# v2 schema: rules on Alert, events in AlertEvent, prices on FactListing / FactPrice.
_TABLES = (
    Alert.__tablename__,
    AlertEvent.__tablename__,
    FactListing.__tablename__,
    FactPrice.__tablename__,
)


@celery_app.task
def check_alerts(
    listing_id: str,
    old_price: str | None,
    new_price: str,
    promo_label: str,
    old_in_stock: str | None = None,
    new_in_stock: str | None = None,
) -> None:
    """Evaluate alert rules when a listing price changes (full wiring pending)."""
    _ = listing_id, old_price, new_price, promo_label, old_in_stock, new_in_stock
    logger.warning("check_alerts(%s): tables %s", listing_id, _TABLES)


@celery_app.task(name="generate_alert_ai_explanation")
def generate_alert_ai_explanation(alert_event_id: int) -> None:
    """Generate AI explanation for an alert event."""
    logger.warning("generate_alert_ai_explanation(%s) pending", alert_event_id)
