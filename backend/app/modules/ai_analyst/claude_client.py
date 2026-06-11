"""Anthropic model-id resolver.

AI1 trimmed this file to a single public function (`resolve_claude_model`) and
its internal helpers. The DA1-orphan digest functions (generate_digest,
_fallback_digest, _parse_json_response) were removed in AI1.
"""

from datetime import datetime, timedelta, timezone

import httpx

ANTHROPIC_MODELS_URL: str = "https://api.anthropic.com/v1/models"
ANTHROPIC_API_VERSION: str = "2023-06-01"

# Default HTTP timeout for Anthropic model-list lookups. Tight enough to fail
# fast on outages, loose enough to ride out a normal cold-start round trip.
ANTHROPIC_HTTP_TIMEOUT_SECONDS: float = 15.0

# Cached resolved model id is reused for this long before re-querying /v1/models.
_MODEL_CACHE_TTL: timedelta = timedelta(hours=6)
_cached_model_id: str | None = None
_cached_model_until: datetime | None = None


def _parse_model_preference(raw: str | None) -> tuple[bool, str | None]:
    """Parse CLAUDE_MODEL into (auto_mode, family).

    - "" / None / "auto"         -> (True, None)  pick latest across families
    - "auto:<family>"            -> (True, family) pick latest in family
    - any other explicit string  -> (False, None)  return as-is
    """
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
    """Fetch the most recently-created Claude model id, optionally filtered
    by family substring (e.g. ``haiku`` / ``opus``)."""
    async with httpx.AsyncClient(timeout=ANTHROPIC_HTTP_TIMEOUT_SECONDS) as client:
        response = await client.get(
            ANTHROPIC_MODELS_URL,
            headers={
                "x-api-key": api_key,
                "anthropic-version": ANTHROPIC_API_VERSION,
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
    """Resolve the model id for Anthropic calls.

    - explicit CLAUDE_MODEL value -> returned as-is.
    - CLAUDE_MODEL=auto[:family]  -> latest model from /v1/models (cached for
      _MODEL_CACHE_TTL).
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
