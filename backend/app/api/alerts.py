"""Alerts API endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, DbSession
from app.models import Alert, AlertEvent, CompetitorProduct, Product
from app.schemas.alert import (
    AlertCreate,
    AlertEventResponse,
    AlertResponse,
    AlertUpdate,
)

router = APIRouter()


@router.get("/", response_model=list[AlertResponse])
async def list_alerts(
    current_user: CurrentUser,
    db: DbSession,
) -> list[AlertResponse]:
    """List alerts of current user."""
    result = await db.execute(
        select(Alert)
        .where(Alert.user_id == current_user.id)
        .options(selectinload(Alert.product))
    )
    alerts = result.scalars().all()
    return [
        AlertResponse(
            id=a.id,
            product_id=a.product_id,
            product_name=a.product.name if a.product else None,
            type=a.type,
            threshold_percent=float(a.threshold_percent) if a.threshold_percent else None,
            channel=a.channel,
            is_active=a.is_active,
            created_at=a.created_at,
        )
        for a in alerts
    ]


@router.post("/", response_model=AlertResponse, status_code=status.HTTP_201_CREATED)
async def create_alert(
    data: AlertCreate,
    current_user: CurrentUser,
    db: DbSession,
) -> AlertResponse:
    """Create new alert."""
    if data.product_id:
        product_result = await db.execute(
            select(Product).where(
                Product.id == data.product_id,
                Product.user_id == current_user.id,
            )
        )
        product = product_result.scalar_one_or_none()
        if product is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
        product_name = product.name
    else:
        product_name = None

    alert = Alert(
        user_id=current_user.id,
        product_id=data.product_id,
        type=data.type,
        threshold_percent=data.threshold_percent,
        channel=data.channel,
    )
    db.add(alert)
    await db.flush()
    return AlertResponse(
        id=alert.id,
        product_id=alert.product_id,
        product_name=product_name,
        type=alert.type,
        threshold_percent=float(alert.threshold_percent) if alert.threshold_percent else None,
        channel=alert.channel,
        is_active=alert.is_active,
        created_at=alert.created_at,
    )


@router.put("/{id}", response_model=AlertResponse)
async def update_alert(
    id: UUID,
    data: AlertUpdate,
    current_user: CurrentUser,
    db: DbSession,
) -> AlertResponse:
    """Update alert (e.g. toggle is_active)."""
    result = await db.execute(
        select(Alert)
        .where(Alert.id == id, Alert.user_id == current_user.id)
        .options(selectinload(Alert.product))
    )
    alert = result.scalar_one_or_none()
    if alert is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")

    if data.is_active is not None:
        alert.is_active = data.is_active
    await db.flush()

    return AlertResponse(
        id=alert.id,
        product_id=alert.product_id,
        product_name=alert.product.name if alert.product else None,
        type=alert.type,
        threshold_percent=float(alert.threshold_percent) if alert.threshold_percent else None,
        channel=alert.channel,
        is_active=alert.is_active,
        created_at=alert.created_at,
    )


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_alert(
    id: UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> None:
    """Delete alert."""
    result = await db.execute(
        select(Alert).where(Alert.id == id, Alert.user_id == current_user.id)
    )
    alert = result.scalar_one_or_none()
    if alert is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")
    await db.delete(alert)


@router.get("/events", response_model=list[AlertEventResponse])
async def list_alert_events(
    current_user: CurrentUser,
    db: DbSession,
    limit: int = Query(20, ge=1, le=100),
) -> list[AlertEventResponse]:
    """List recent alert events (last 20 by default)."""
    result = await db.execute(
        select(AlertEvent)
        .join(Alert, AlertEvent.alert_id == Alert.id)
        .where(Alert.user_id == current_user.id)
        .options(
            selectinload(AlertEvent.alert).selectinload(Alert.product),
            selectinload(AlertEvent.competitor_product).selectinload(CompetitorProduct.competitor),
        )
        .order_by(AlertEvent.triggered_at.desc())
        .limit(limit)
    )
    events_list = result.scalars().unique().all()
    return [
        AlertEventResponse(
            id=ev.id,
            alert_id=ev.alert_id,
            product_name=ev.alert.product.name if ev.alert and ev.alert.product else None,
            competitor_name=(
                ev.competitor_product.competitor.name
                if ev.competitor_product and ev.competitor_product.competitor
                else None
            ),
            old_price=ev.old_price,
            new_price=ev.new_price,
            message=ev.message,
            sent_via=ev.sent_via,
            triggered_at=ev.triggered_at,
        )
        for ev in events_list
    ]
