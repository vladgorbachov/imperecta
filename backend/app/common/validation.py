"""Shared input validators (Tier-0).

CORE-AUTH1 lifted the language + ai_tone validators out of core.schemas into
this neutral location so both ``app.modules.auth.schemas.UserRegister`` and
``app.modules.core.schemas.UserUpdate`` can import them without creating a
core <-> auth import cycle.

ai_tone values mirror the ORM CheckConstraint ``ck_users_ai_tone``.
"""

from typing import Final

SUPPORTED_LANGUAGES: Final[list[str]] = ["en", "ar", "es", "zh", "ru", "fr", "ro", "uk"]
ALLOWED_LANGUAGE_CODES: Final[frozenset[str]] = frozenset(SUPPORTED_LANGUAGES)
AI_TONE_VALUES: Final[frozenset[str]] = frozenset({"concise", "balanced", "detailed"})


def validate_language(value: str) -> str:
    """Reject any language code outside SUPPORTED_LANGUAGES."""
    if value not in ALLOWED_LANGUAGE_CODES:
        allowed = ", ".join(sorted(ALLOWED_LANGUAGE_CODES))
        raise ValueError(f"Invalid language. Allowed: {allowed}")
    return value


def validate_ai_tone(value: str) -> str:
    """Reject any ai_tone value outside AI_TONE_VALUES (mirrors the ORM check)."""
    if value not in AI_TONE_VALUES:
        raise ValueError("Invalid ai_tone. Allowed: concise, balanced, detailed")
    return value
