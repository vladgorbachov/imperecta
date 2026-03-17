"""Digest business logic."""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import PriceSnapshot, Product, User
from app.modules.ai_analyst.service import generate_digest as ai_generate_digest
from app.modules.alerts.notifications import send_digest, send_digest_email_to_user
from app.modules.digests.models import Digest


async def collect_period_data(session: AsyncSession, user_id: UUID, period_start: datetime, period_end: datetime) -> dict:
    from app.models import CompetitorProduct

    price_changes = []
    new_promos = []
    out_of_stock = []
    rows = (
        await session.execute(
            select(CompetitorProduct, Product.name).join(Product, CompetitorProduct.product_id == Product.id).where(Product.user_id == user_id)
        )
    ).all()
    for cp, product_name in rows:
        snapshots = (
            await session.execute(
                select(PriceSnapshot)
                .where(PriceSnapshot.competitor_product_id == cp.id, PriceSnapshot.scraped_at >= period_start, PriceSnapshot.scraped_at <= period_end)
                .order_by(PriceSnapshot.scraped_at.asc())
            )
        ).scalars().all()
        for snap in snapshots:
            if snap.old_price and snap.old_price > 0 and snap.price != snap.old_price:
                change_pct = float((snap.old_price - snap.price) / snap.old_price * 100)
                price_changes.append({"product_name": product_name, "change": f"{snap.old_price} → {snap.price} ({change_pct:+.1f}%)", "change_percent": change_pct})
            if snap.promo_label:
                new_promos.append({"product_name": product_name, "promo_label": snap.promo_label})
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


async def send_digest_for_user(session: AsyncSession, user: "User", content_md: str, period: str) -> None:
    subject = f"Imperecta: {period.capitalize()} digest"
    send_digest_email_to_user(user.id, subject, content_md)
    if user.telegram_chat_id:
        await send_digest(user.telegram_chat_id, content_md[:3000] if len(content_md) > 3000 else content_md)


async def generate_and_store_digest(session: AsyncSession, user: "User", period_type: str, period_start: datetime, period_end: datetime) -> Digest:
    data = await collect_period_data(session, user.id, period_start, period_end)
    content_md = await ai_generate_digest(user.id, data, db=session, user=user)
    digest = Digest(
        user_id=user.id,
        period_type=period_type,
        period_start=period_start,
        period_end=period_end,
        content_md=content_md,
    )
    session.add(digest)
    await session.flush()
    await send_digest_for_user(session, user, content_md, period_type)
    digest.sent_at = datetime.now(timezone.utc)
    return digest
