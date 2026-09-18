"""User price-alert rules: operational reads + gated writes (P3).

Reads are user-scoped SELECTs with display-label joins; every write goes
through the ALERT door (authorize_alert_write -> gate.exec_write). Ownership:
list/update/delete always filter by the authenticated user's id — a foreign
rule id behaves exactly like a missing one.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.app_tables import Alert, AlertEvent
from app.models.dimensions import DimMarketplace, DimProduct
from app.models.facts import FactListing
from app.modules.persist.alerts_write import build_alert_rule_fields, write_alert_async

_RULE_LABEL_COLUMNS = (
    Alert,
    DimProduct.name.label("product_title"),
    DimMarketplace.name.label("marketplace_name"),
)


def rule_channels(rule: Alert) -> list[str]:
    """Effective enabled channel set: `channels` when set, else [channel].

    Shared with the trigger engine so delivery fan-out and API responses
    agree on the fallback for pre-P15 rows.
    """
    raw = rule.channels
    if isinstance(raw, list) and raw:
        return [str(name) for name in raw]
    return [rule.channel or "email"]


def normalize_channels(payload: dict[str, Any]) -> list[str]:
    """Deduped (order-preserving) channel set from a create payload."""
    raw = payload.get("channels") or [payload.get("channel") or "email"]
    return list(dict.fromkeys(str(name) for name in raw))


class AlertRulesService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    def _labelled_rules_stmt(self, user_id: UUID):
        return (
            select(*_RULE_LABEL_COLUMNS)
            .select_from(Alert)
            .outerjoin(DimProduct, Alert.product_id == DimProduct.id)
            .outerjoin(DimMarketplace, Alert.marketplace_id == DimMarketplace.id)
            .where(Alert.user_id == user_id, Alert.alert_class == "analytic")
        )

    @staticmethod
    def _rule_to_dict(
        rule: Alert,
        product_title: str | None,
        marketplace_name: str | None,
    ) -> dict[str, Any]:
        return {
            "id": rule.id,
            "listing_id": rule.listing_id,
            "product_id": rule.product_id,
            "marketplace_id": rule.marketplace_id,
            "alert_type": rule.alert_type,
            "threshold_pct": float(rule.threshold_pct) if rule.threshold_pct is not None else None,
            "channel": rule.channel or "email",
            "channels": rule_channels(rule),
            "webhook_url": rule.webhook_url,
            "cooldown_minutes": int(rule.cooldown_minutes or 60),
            "is_active": bool(rule.is_active),
            "last_triggered_at": rule.last_triggered_at,
            "trigger_count": int(rule.trigger_count or 0),
            "created_at": rule.created_at,
            "product_title": product_title,
            "marketplace_name": marketplace_name,
        }

    async def list_rules(self, user_id: UUID) -> tuple[list[dict[str, Any]], int]:
        stmt = self._labelled_rules_stmt(user_id).order_by(Alert.created_at.desc())
        rows = (await self.db.execute(stmt)).all()
        items = [self._rule_to_dict(rule, title, mp_name) for rule, title, mp_name in rows]
        return items, len(items)

    async def get_rule(self, user_id: UUID, rule_id: UUID) -> dict[str, Any] | None:
        stmt = self._labelled_rules_stmt(user_id).where(Alert.id == rule_id)
        row = (await self.db.execute(stmt)).first()
        if row is None:
            return None
        rule, title, mp_name = row
        return self._rule_to_dict(rule, title, mp_name)

    async def _resolve_product_id(self, payload: dict[str, Any]) -> None:
        """Derive product_id from listing_id when the client sent only the listing."""
        if payload.get("product_id") is not None or payload.get("listing_id") is None:
            return
        product_id = await self.db.scalar(
            select(FactListing.product_id).where(FactListing.id == payload["listing_id"])
        )
        if product_id is not None:
            payload["product_id"] = product_id

    async def create_rule(self, user_id: UUID, payload: dict[str, Any]) -> dict[str, Any] | None:
        await self._resolve_product_id(payload)
        rule_id = uuid4()
        fields = build_alert_rule_fields(
            id=rule_id,
            user_id=user_id,
            listing_id=payload.get("listing_id"),
            product_id=payload.get("product_id"),
            marketplace_id=payload.get("marketplace_id"),
            alert_type=payload["alert_type"],
            threshold_pct=payload.get("threshold_pct"),
            channel=payload.get("channel") or "email",
            channels=normalize_channels(payload),
            webhook_url=payload.get("webhook_url"),
            cooldown_minutes=int(payload.get("cooldown_minutes") or 60),
            is_active=True,
            trigger_count=0,
            alert_class="analytic",
        )
        fields = {k: v for k, v in fields.items() if v is not None}
        result = await write_alert_async(
            kind="rule_create",
            fields=fields,
            reject_source="alerts_rule_create",
        )
        if not result.ok:
            return None
        return await self.get_rule(user_id, rule_id)

    async def update_rule(
        self, user_id: UUID, rule_id: UUID, delta: dict[str, Any]
    ) -> dict[str, Any] | None:
        owned = await self.get_rule(user_id, rule_id)
        if owned is None:
            return None
        changes = {k: v for k, v in delta.items() if v is not None}
        if not changes:
            return owned
        if changes.get("channels"):
            changes["channels"] = list(
                dict.fromkeys(str(name) for name in changes["channels"])
            )
        fields = build_alert_rule_fields(id=rule_id, **changes)
        result = await write_alert_async(
            kind="rule_update",
            fields=fields,
            reject_source="alerts_rule_update",
        )
        if not result.ok:
            return None
        return await self.get_rule(user_id, rule_id)

    async def delete_rule(self, user_id: UUID, rule_id: UUID) -> bool:
        owned = await self.get_rule(user_id, rule_id)
        if owned is None:
            return False
        result = await write_alert_async(
            kind="rule_delete",
            fields=build_alert_rule_fields(id=rule_id),
            reject_source="alerts_rule_delete",
        )
        return bool(result.ok)

    async def list_events(
        self, user_id: UUID, *, limit: int, offset: int
    ) -> tuple[list[dict[str, Any]], int]:
        base = (
            select(
                AlertEvent,
                Alert.alert_type,
                DimProduct.name.label("product_title"),
                DimMarketplace.name.label("marketplace_name"),
                FactListing.last_currency_code.label("currency"),
            )
            .select_from(AlertEvent)
            .join(Alert, AlertEvent.alert_id == Alert.id)
            .outerjoin(FactListing, AlertEvent.listing_id == FactListing.id)
            .outerjoin(DimProduct, Alert.product_id == DimProduct.id)
            .outerjoin(DimMarketplace, Alert.marketplace_id == DimMarketplace.id)
            .where(Alert.user_id == user_id, Alert.alert_class == "analytic")
        )
        total = int(
            await self.db.scalar(
                select(func.count())
                .select_from(AlertEvent)
                .join(Alert, AlertEvent.alert_id == Alert.id)
                .where(Alert.user_id == user_id, Alert.alert_class == "analytic")
            )
            or 0
        )
        rows = (
            await self.db.execute(
                base.order_by(AlertEvent.triggered_at.desc()).limit(limit).offset(offset)
            )
        ).all()
        items = [
            {
                "id": event.id,
                "rule_id": event.alert_id,
                "alert_type": alert_type,
                "product_title": product_title,
                "marketplace_name": marketplace_name,
                "old_price": float(event.old_value) if event.old_value is not None else None,
                "new_price": float(event.new_value) if event.new_value is not None else None,
                "currency": currency,
                "change_pct": float(event.change_pct) if event.change_pct is not None else None,
                "triggered_at": event.triggered_at,
            }
            for event, alert_type, product_title, marketplace_name, currency in rows
        ]
        return items, total
