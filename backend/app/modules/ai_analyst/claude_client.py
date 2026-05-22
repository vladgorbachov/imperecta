"""Claude API integration for digest generation."""

import json
import logging
import re
from datetime import datetime, timedelta, timezone
from uuid import UUID

import anthropic
import httpx

from app.config import Settings

logger = logging.getLogger(__name__)
settings = Settings()

_MODEL_CACHE_TTL = timedelta(hours=6)
_cached_model_id: str | None = None
_cached_model_until: datetime | None = None


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


def _parse_model_preference(raw: str | None) -> tuple[bool, str | None]:
    """Parse CLAUDE_MODEL into explicit/auto mode and optional family."""
    value = (raw or "").strip()
    if not value:
        return True, None
    lowered = value.lower()
    if lowered == "auto":
        return True, None
    if lowered.startswith("auto:"):
        family = lowered.split(":", 1)[1].strip()
        return True, family or None
    return False, None


async def _fetch_latest_model_id(api_key: str, family: str | None) -> str:
    """Fetch latest available Claude model id from Anthropic models API."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(
            "https://api.anthropic.com/v1/models",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
        )
    response.raise_for_status()
    payload = response.json()
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, list):
        raise ValueError("Anthropic models response is invalid")

    candidates: list[tuple[datetime, str]] = []
    family_filter = (family or "").strip().lower()
    for item in data:
        if not isinstance(item, dict):
            continue
        model_id = str(item.get("id") or "").strip()
        if not model_id or not model_id.startswith("claude-"):
            continue
        if family_filter and family_filter not in model_id.lower():
            continue
        created_at_raw = str(item.get("created_at") or "")
        try:
            created_at = datetime.fromisoformat(created_at_raw.replace("Z", "+00:00"))
        except ValueError:
            created_at = datetime.min.replace(tzinfo=timezone.utc)
        candidates.append((created_at, model_id))

    if not candidates:
        scope = f" for family '{family_filter}'" if family_filter else ""
        raise ValueError(f"No Claude models available{scope}")

    candidates.sort(key=lambda row: row[0], reverse=True)
    return candidates[0][1]


async def resolve_claude_model(raw_model: str | None, api_key: str | None) -> str:
    """
    Resolve model id for Anthropic calls.
    - explicit CLAUDE_MODEL value -> returned as is
    - CLAUDE_MODEL=auto[:family] -> latest model from /v1/models
    """
    global _cached_model_id, _cached_model_until

    auto_mode, family = _parse_model_preference(raw_model)
    if not auto_mode:
        return (raw_model or "").strip()
    if not api_key:
        raise ValueError("CLAUDE_API_KEY is required when CLAUDE_MODEL is auto")

    now = datetime.now(timezone.utc)
    if _cached_model_id and _cached_model_until and now < _cached_model_until:
        return _cached_model_id

    model_id = await _fetch_latest_model_id(api_key, family)
    _cached_model_id = model_id
    _cached_model_until = now + _MODEL_CACHE_TTL
    return model_id


async def generate_digest(user_id: UUID, period_data: dict, db=None, user=None) -> str:
    _ = user_id
    _ = db
    _ = user
    if not settings.claude_api_key:
        return _fallback_digest(period_data)
    model_id = await resolve_claude_model(settings.claude_model, settings.claude_api_key)
    client = anthropic.AsyncAnthropic(api_key=settings.claude_api_key)
    response = await client.messages.create(
        model=model_id,
        max_tokens=2048,
        system="Ты — аналитик конкурентной разведки. Пиши на русском языке.",
        messages=[{"role": "user", "content": json.dumps(period_data, ensure_ascii=False)}],
    )
    return (response.content[0].text if response.content else "").strip() or _fallback_digest(period_data)
