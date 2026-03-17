"""Claude API integration for digest generation."""

import json
import logging
import re
from uuid import UUID

import anthropic

from app.config import Settings

logger = logging.getLogger(__name__)
settings = Settings()


def _parse_json_response(text: str) -> dict:
    match = re.search(r"\{[^{}]*\}", text.strip(), re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    return {}


def _fallback_digest(period_data: dict) -> str:
    lines = ["# Дайджест", ""]
    for item in period_data.get("top_changes", [])[:5]:
        lines.append(f"- {item.get('product_name', 'Товар')}: {item.get('change', '')}")
    if len(lines) <= 2:
        lines.append("Нет значимых изменений за период.")
    return "\n".join(lines)


async def generate_digest(user_id: UUID, period_data: dict, db=None, user=None) -> str:
    _ = user_id
    _ = db
    _ = user
    if not settings.claude_api_key:
        return _fallback_digest(period_data)
    client = anthropic.AsyncAnthropic(api_key=settings.claude_api_key)
    response = await client.messages.create(
        model=settings.claude_model,
        max_tokens=2048,
        system="Ты — аналитик конкурентной разведки. Пиши на русском языке.",
        messages=[{"role": "user", "content": json.dumps(period_data, ensure_ascii=False)}],
    )
    return (response.content[0].text if response.content else "").strip() or _fallback_digest(period_data)
