"""AI analyst services: chat and helpers (v2 migration stubs)."""

import json
import logging
import re
import time
from uuid import UUID

from anthropic import AsyncAnthropic
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models.app_tables import AIChatMessage, AIChatSession, ApiLog
from app.models.core import UserProduct
from app.modules.ai_analyst.claude_client import resolve_claude_model

logger = logging.getLogger(__name__)
settings = Settings()

SYSTEM_PROMPT = """You are Imperecta AI Analyst. Answer in user's language and use markdown."""


def _get_client() -> AsyncAnthropic | None:
    if not settings.claude_api_key:
        return None
    return AsyncAnthropic(api_key=settings.claude_api_key)


async def build_user_context(db: AsyncSession, user_id: UUID, context_type: str | None = None, context_id: UUID | None = None) -> str:
    _ = context_type, context_id
    count = (
        await db.execute(select(func.count()).select_from(UserProduct).where(UserProduct.user_id == user_id))
    ).scalar() or 0
    if count:
        return f"User tracks {count} canonical product(s) (dim_product links). v2 migration in progress."
    return "No tracked products yet."


async def chat(
    db: AsyncSession,
    user,
    session_id: UUID | None,
    message: str,
    context_type: str = "general",
    context_id: UUID | None = None,
) -> dict:
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
        session = AIChatSession(user_id=user.id, context_type=context_type, title=message[:100])
        db.add(session)
        await db.flush()

    db.add(AIChatMessage(session_id=session.id, role="user", content=message))
    await db.flush()
    context = await build_user_context(db, user.id, context_type, context_id)
    history = list(
        reversed(
            (
                await db.execute(
                    select(AIChatMessage)
                    .where(AIChatMessage.session_id == session.id)
                    .order_by(AIChatMessage.created_at.desc())
                    .limit(20)
                )
            ).scalars().all()
        )
    )
    messages = [{"role": m.role, "content": m.content} for m in history]
    model_id = await resolve_claude_model(settings.claude_model, settings.claude_api_key)
    start = time.time()
    response = await client.messages.create(
        model=model_id,
        max_tokens=2000,
        system=f"{SYSTEM_PROMPT}\n{context}",
        messages=messages,
    )
    duration_ms = int((time.time() - start) * 1000)
    assistant_content = response.content[0].text if response.content else ""
    tokens = (response.usage.input_tokens or 0) + (response.usage.output_tokens or 0) if response.usage else 0
    db.add(
        ApiLog(
            service="claude",
            endpoint="/v1/messages",
            status="success",
            status_code=200,
            duration_ms=duration_ms,
            tokens_used=tokens,
        )
    )
    db.add(AIChatMessage(session_id=session.id, role="assistant", content=assistant_content))
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
    model_id = await resolve_claude_model(settings.claude_model, settings.claude_api_key)
    response = await client.messages.create(model=model_id, max_tokens=512, messages=[{"role": "user", "content": prompt}])
    text = response.content[0].text if response.content else "[]"
    match = re.search(r"\[[\s\S]*\]", text)
    suggestions = json.loads(match.group()) if match else []
    by_idx = {s["index"]: s.get("suggested_category") for s in suggestions if isinstance(s, dict)}
    return [{**p, "suggested_category": by_idx.get(i)} for i, p in enumerate(products)]


async def get_price_recommendation(db: AsyncSession, product_id: UUID, user_id: UUID) -> dict:
    _ = db, product_id, user_id
    raise NotImplementedError("Pending migration to v2 schema")


async def get_products_at_risk(db: AsyncSession, user_id: UUID, limit: int = 5) -> list[dict]:
    _ = db, user_id, limit
    return []
