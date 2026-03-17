"""AI analyst services: chat, digest, product AI helpers."""

import json
import logging
import re
import time
from uuid import UUID

from anthropic import AsyncAnthropic
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models import Competitor, CompetitorProduct, Product
from app.modules.ai_analyst.models import AIChatMessage, AIChatSession
from app.modules.core.models import ApiLog
from app.modules.dashboard.service import DashboardService

logger = logging.getLogger(__name__)
settings = Settings()

SYSTEM_PROMPT = """You are Imperecta AI Analyst. Answer in user's language and use markdown."""


def _get_client() -> AsyncAnthropic | None:
    if not settings.claude_api_key:
        return None
    return AsyncAnthropic(api_key=settings.claude_api_key)


async def build_user_context(db: AsyncSession, user_id: UUID, context_type: str | None = None, context_id: UUID | None = None) -> str:
    _ = context_type
    _ = context_id
    parts = []
    product_list = (
        await db.execute(select(Product).where(Product.user_id == user_id, Product.is_active.is_(True)).limit(50))
    ).scalars().all()
    if product_list:
        parts.append(f"User has {len(product_list)} products.")
    comp_list = (await db.execute(select(Competitor).where(Competitor.user_id == user_id).limit(30))).scalars().all()
    if comp_list:
        parts.append(f"User monitors {len(comp_list)} competitors.")
    anomalies = await DashboardService(db, user_id).get_anomalies(limit=5)
    if anomalies:
        parts.append("Recent anomalies:")
        for anomaly in anomalies:
            parts.append(f"- {anomaly['product_name']}: {anomaly['change_percent']:+.1f}%")
    return "\n".join(parts) if parts else "No data available yet."


async def chat(db: AsyncSession, user, session_id: int | None, message: str, context_type: str = "general", context_id: UUID | None = None) -> dict:
    client = _get_client()
    if not client:
        raise ValueError("Claude API key not configured")
    if session_id:
        session = (
            await db.execute(select(AIChatSession).where(AIChatSession.id == session_id, AIChatSession.user_id == user.id))
        ).scalar_one_or_none()
        if not session:
            raise ValueError("Session not found")
    else:
        session = AIChatSession(user_id=user.id, context_type=context_type, context_id=context_id, title=message[:100])
        db.add(session)
        await db.flush()

    db.add(AIChatMessage(session_id=session.id, role="user", content=message))
    await db.flush()
    context = await build_user_context(db, user.id, context_type, context_id)
    history = list(
        reversed(
            (
                await db.execute(
                    select(AIChatMessage).where(AIChatMessage.session_id == session.id).order_by(AIChatMessage.created_at.desc()).limit(20)
                )
            ).scalars().all()
        )
    )
    messages = [{"role": m.role, "content": m.content} for m in history]
    start = time.time()
    response = await client.messages.create(
        model=settings.claude_model,
        max_tokens=2000,
        system=f"{SYSTEM_PROMPT}\n{context}",
        messages=messages,
    )
    duration_ms = int((time.time() - start) * 1000)
    assistant_content = response.content[0].text if response.content else ""
    tokens = (response.usage.input_tokens or 0) + (response.usage.output_tokens or 0)
    db.add(ApiLog(service="claude", endpoint="/v1/messages", status="success", status_code=200, duration_ms=duration_ms, tokens_used=tokens))
    db.add(AIChatMessage(session_id=session.id, role="assistant", content=assistant_content, tokens_used=tokens, duration_ms=duration_ms))
    await db.flush()
    return {"session_id": session.id, "response": assistant_content, "tokens_used": tokens, "duration_ms": duration_ms}


async def auto_categorize(products: list[dict]) -> list[dict]:
    if not products:
        return []
    if not settings.claude_api_key:
        return [{**p, "suggested_category": None} for p in products]
    client = AsyncAnthropic(api_key=settings.claude_api_key)
    items = [{"name": p.get("name", ""), "sku": p.get("sku", ""), "price": str(p.get("price", ""))} for p in products]
    prompt = f"""Given these products, suggest short category name. JSON array with index/suggested_category. Products: {json.dumps(items, ensure_ascii=False)}"""
    response = await client.messages.create(model=settings.claude_model, max_tokens=512, messages=[{"role": "user", "content": prompt}])
    text = response.content[0].text if response.content else "[]"
    match = re.search(r"\[[\s\S]*\]", text)
    suggestions = json.loads(match.group()) if match else []
    by_idx = {s["index"]: s.get("suggested_category") for s in suggestions if isinstance(s, dict)}
    return [{**p, "suggested_category": by_idx.get(i)} for i, p in enumerate(products)]


async def get_price_recommendation(db: AsyncSession, product_id: UUID, user_id: UUID) -> dict:
    product = (await db.execute(select(Product).where(Product.id == product_id, Product.user_id == user_id))).scalar_one_or_none()
    if not product:
        raise ValueError("Product not found")
    my_price = float(product.current_price) if product.current_price else 0
    competitor_prices = [
        float(r[0])
        for r in (
            await db.execute(
                select(CompetitorProduct.last_price)
                .join(Product, CompetitorProduct.product_id == Product.id)
                .where(CompetitorProduct.product_id == product_id, Product.user_id == user_id, CompetitorProduct.is_active.is_(True))
            )
        ).all()
        if r[0] is not None
    ]
    avg = sum(competitor_prices) / len(competitor_prices) if competitor_prices else my_price
    return {"recommended_price": round(avg, 2), "reasoning": "Competitor average", "confidence": 0.5}


async def get_products_at_risk(db: AsyncSession, user_id: UUID, limit: int = 5) -> list[dict]:
    rows = (
        await db.execute(select(Product).where(Product.user_id == user_id, Product.is_active.is_(True)).limit(limit))
    ).scalars().all()
    return [{"product_id": str(p.id), "product_name": p.name, "risk_score": 0.0} for p in rows]
