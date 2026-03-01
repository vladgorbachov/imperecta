"""Claude API integration for AI digest generation."""

import json
import logging
from uuid import UUID

import anthropic

from app.config import Settings

logger = logging.getLogger(__name__)
settings = Settings()

SYSTEM_PROMPT = """Ты — аналитик конкурентной разведки. Пиши на русском языке.
Генерируй краткий, полезный дайджест изменений цен для e-commerce бизнеса.
Формат: markdown. Структура: Ключевые изменения, Акции конкурентов,
Рекомендации по ценообразованию, Аномалии (если есть)."""


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


async def generate_digest(user_id: UUID, period_data: dict) -> str:
    """
    Generate digest markdown using Anthropic Claude API.
    period_data: { top_changes, promos, anomalies, summary_stats }
    Returns markdown string. Fallback to template on error.
    """
    if not settings.claude_api_key:
        logger.warning("CLAUDE_API_KEY not set, using fallback digest")
        return _fallback_digest(period_data)

    user_prompt = json.dumps(period_data, ensure_ascii=False, indent=2)

    try:
        client = anthropic.AsyncAnthropic(api_key=settings.claude_api_key)
        response = await client.messages.create(
            model=settings.claude_model,
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
        text = response.content[0].text if response.content else ""
        return text.strip() or _fallback_digest(period_data)
    except anthropic.APIError as e:
        logger.warning("Claude API error: %s", e)
        return _fallback_digest(period_data)
    except Exception as e:
        logger.warning("Digest generation error: %s", e)
        return _fallback_digest(period_data)
