"""Claude API integration for AI digest generation."""

import json
import logging
import time
from uuid import UUID

import anthropic
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings

logger = logging.getLogger(__name__)
settings = Settings()

SYSTEM_PROMPT_BASE = """Ты — аналитик конкурентной разведки. Пиши на русском языке.
Генерируй краткий, полезный дайджест изменений цен для e-commerce бизнеса.
Формат: markdown. Структура: Ключевые изменения, Акции конкурентов,
Рекомендации по ценообразованию, Аномалии (если есть)."""

AI_TONE_INSTRUCTIONS = {
    "conservative": "Be cautious. Emphasize risks. Recommend minimal changes.",
    "balanced": "Be objective. Present both opportunities and risks.",
    "aggressive": "Focus on growth opportunities. Recommend bold moves.",
}


async def _log_api_call(
    db: AsyncSession,
    service: str,
    status: str,
    duration_ms: int,
    *,
    error: str | None = None,
    tokens: int | None = None,
    status_code: int | None = None,
    endpoint: str | None = None,
) -> None:
    """Log external API call to api_logs table."""
    from app.models.api_log import ApiLog

    log = ApiLog(
        service=service,
        endpoint=endpoint,
        status=status,
        status_code=status_code,
        error_message=error,
        duration_ms=duration_ms,
        tokens_used=tokens,
    )
    db.add(log)


def _fallback_digest(period_data: dict) -> str:
    """Template digest when AI fails."""
    lines = ["# Дайджест", ""]
    if period_data.get("top_changes"):
        lines.append("## Ключевые изменения")
        for item in period_data["top_changes"][:5]:
            lines.append(f"- {item.get('product_name', 'Товар')}: {item.get('change', '')}")
        lines.append("")
    if period_data.get("promos"):
        lines.append("## Акции конкурентов")
        for item in period_data["promos"][:5]:
            lines.append(f"- {item.get('product_name', 'Товар')}: {item.get('promo_label', '')}")
        lines.append("")
    if period_data.get("anomalies"):
        lines.append("## Аномалии")
        for item in period_data["anomalies"][:5]:
            lines.append(f"- {item.get('product_name', 'Товар')}: {item.get('change_percent', 0):.1f}%")
    if len(lines) <= 2:
        lines.append("Нет значимых изменений за период.")
    return "\n".join(lines)


def _build_system_prompt(ai_tone: str = "balanced") -> str:
    """Build system prompt with ai_tone instruction."""
    tone_instruction = AI_TONE_INSTRUCTIONS.get(
        ai_tone, AI_TONE_INSTRUCTIONS["balanced"]
    )
    return f"{SYSTEM_PROMPT_BASE}\n\nTone: {tone_instruction}"


async def generate_digest(
    user_id: UUID,
    period_data: dict,
    db: AsyncSession | None = None,
    user=None,
) -> str:
    """
    Generate digest markdown using Anthropic Claude API.
    period_data: { top_changes, promos, anomalies, summary_stats }
    user: User model instance for ai_tone. If None and db provided, fetches from DB.
    Returns markdown string. Fallback to template on error.
    Logs API calls to api_logs when db session is provided.
    """
    if not settings.claude_api_key:
        logger.warning("CLAUDE_API_KEY not set, using fallback digest")
        return _fallback_digest(period_data)

    ai_tone = "balanced"
    if user:
        ai_tone = getattr(user, "ai_tone", "balanced") or "balanced"
    elif db:
        from app.models import User

        user_result = await db.execute(select(User).where(User.id == user_id))
        u = user_result.scalar_one_or_none()
        if u:
            ai_tone = getattr(u, "ai_tone", "balanced") or "balanced"

    system_prompt = _build_system_prompt(ai_tone)
    user_prompt = json.dumps(period_data, ensure_ascii=False, indent=2)
    start = time.time()

    try:
        client = anthropic.AsyncAnthropic(api_key=settings.claude_api_key)
        response = await client.messages.create(
            model=settings.claude_model,
            max_tokens=2048,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        duration_ms = int((time.time() - start) * 1000)
        tokens = 0
        if response.usage:
            tokens = (response.usage.input_tokens or 0) + (response.usage.output_tokens or 0)
        if db:
            await _log_api_call(
                db,
                "claude",
                "success",
                duration_ms,
                tokens=tokens,
                status_code=200,
                endpoint="messages.create",
            )
        text = response.content[0].text if response.content else ""
        return text.strip() or _fallback_digest(period_data)
    except anthropic.APIError as e:
        duration_ms = int((time.time() - start) * 1000)
        status_code = getattr(e, "status_code", None)
        if db:
            await _log_api_call(
                db,
                "claude",
                "error",
                duration_ms,
                error=str(e),
                status_code=status_code,
                endpoint="messages.create",
            )
        logger.warning("Claude API error: %s", e)
        return _fallback_digest(period_data)
    except Exception as e:
        duration_ms = int((time.time() - start) * 1000)
        if db:
            await _log_api_call(
                db,
                "claude",
                "error",
                duration_ms,
                error=str(e),
                endpoint="messages.create",
            )
        logger.warning("Digest generation error: %s", e)
        return _fallback_digest(period_data)
