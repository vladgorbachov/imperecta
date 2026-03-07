"""AI chat service: Claude integration for conversational analytics."""

import logging
import time
from uuid import UUID

from anthropic import AsyncAnthropic
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models import Competitor, Product
from app.models.ai_chat import AIChatMessage, AIChatSession
from app.models.api_log import ApiLog

logger = logging.getLogger(__name__)
settings = Settings()

SYSTEM_PROMPT = """You are Imperecta AI Analyst — an expert market intelligence agent for e-commerce businesses.

You have access to the user's data context:
{context}

Your role:
- Analyze price trends, competitor behavior, and market dynamics
- Provide actionable recommendations (specific numbers, percentages)
- Predict market movements based on historical patterns
- Answer in the user's language (detected from their message)
- Use markdown formatting: headers, bullet points, bold for key numbers
- Be concise but data-driven
- When uncertain, state confidence level (e.g., "with ~75% confidence")

Never make up specific prices or dates — use only the data provided in context.
If data is insufficient, say so and suggest what data would help."""


def _get_client() -> AsyncAnthropic | None:
    """Create Anthropic client if API key is configured."""
    if not settings.claude_api_key:
        return None
    return AsyncAnthropic(api_key=settings.claude_api_key)


async def build_user_context(
    db: AsyncSession,
    user_id: UUID,
    context_type: str | None = None,
    context_id: UUID | None = None,
) -> str:
    """Build context string from user's data for Claude."""
    parts = []

    # User's products summary
    products_result = await db.execute(
        select(Product)
        .where(Product.user_id == user_id, Product.is_active.is_(True))
        .limit(50)
    )
    product_list = products_result.scalars().all()
    if product_list:
        parts.append(f"User has {len(product_list)} products.")
        top_5 = product_list[:5]
        parts.append(
            "Top products: "
            + ", ".join(
                f"{p.name} (price: {p.current_price} {p.currency})" for p in top_5
            )
        )

    # Competitors summary
    competitors_result = await db.execute(
        select(Competitor).where(Competitor.user_id == user_id).limit(30)
    )
    comp_list = competitors_result.scalars().all()
    if comp_list:
        parts.append(f"User monitors {len(comp_list)} competitors.")

    # Recent anomalies (reuse dashboard service)
    from app.services.dashboard_service import DashboardService

    ds = DashboardService(db, user_id)
    anomalies = await ds.get_anomalies(limit=5)
    if anomalies:
        parts.append("Recent anomalies (24h):")
        for a in anomalies:
            parts.append(
                f"  - {a['product_name']}: {a['change_percent']:+.1f}% ({a['competitor_name']})"
            )

    # Specific context
    if context_type == "product" and context_id:
        product_result = await db.execute(
            select(Product).where(
                Product.id == context_id,
                Product.user_id == user_id,
            )
        )
        product = product_result.scalar_one_or_none()
        if product:
            parts.append(
                f"\nFocused product: {product.name}, price: {product.current_price} "
                f"{product.currency}, SKU: {product.sku}"
            )

    return "\n".join(parts) if parts else "No data available yet. User just started."


async def chat(
    db: AsyncSession,
    user: "User",
    session_id: int | None,
    message: str,
    context_type: str = "general",
    context_id: UUID | None = None,
) -> dict:
    """
    Send message to Claude and get response. Manages session and history.

    Returns:
        dict with session_id, response, tokens_used, duration_ms
    """
    client = _get_client()
    if not client:
        raise ValueError("Claude API key not configured")

    # Get or create session
    if session_id:
        session_result = await db.execute(
            select(AIChatSession).where(
                AIChatSession.id == session_id,
                AIChatSession.user_id == user.id,
            )
        )
        session = session_result.scalar_one_or_none()
        if not session:
            raise ValueError("Session not found")
    else:
        session = AIChatSession(
            user_id=user.id,
            context_type=context_type,
            context_id=context_id,
            title=message[:100],
        )
        db.add(session)
        await db.flush()

    # Save user message
    user_msg = AIChatMessage(session_id=session.id, role="user", content=message)
    db.add(user_msg)
    await db.flush()

    # Build context
    context = await build_user_context(db, user.id, context_type, context_id)

    # Build message history (last 20 messages for context window)
    history_result = await db.execute(
        select(AIChatMessage)
        .where(AIChatMessage.session_id == session.id)
        .order_by(AIChatMessage.created_at.desc())
        .limit(20)
    )
    history = list(reversed(history_result.scalars().all()))
    messages = [{"role": m.role, "content": m.content} for m in history]

    # Call Claude
    start = time.time()
    try:
        response = await client.messages.create(
            model=settings.claude_model,
            max_tokens=2000,
            system=SYSTEM_PROMPT.format(context=context),
            messages=messages,
        )
        duration_ms = int((time.time() - start) * 1000)
        assistant_content = response.content[0].text
        tokens = response.usage.input_tokens + response.usage.output_tokens

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
    except Exception as e:
        duration_ms = int((time.time() - start) * 1000)
        logger.error("Claude API error in chat: %s", e)

        db.add(
            ApiLog(
                service="claude",
                endpoint="/v1/messages",
                status="error",
                error_message=str(e),
                duration_ms=duration_ms,
            )
        )
        await db.commit()
        raise

    # Save assistant message
    assistant_msg = AIChatMessage(
        session_id=session.id,
        role="assistant",
        content=assistant_content,
        tokens_used=tokens,
        duration_ms=duration_ms,
    )
    db.add(assistant_msg)
    await db.flush()

    return {
        "session_id": session.id,
        "response": assistant_content,
        "tokens_used": tokens,
        "duration_ms": duration_ms,
    }
