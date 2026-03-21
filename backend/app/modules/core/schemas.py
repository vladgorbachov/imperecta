"""Pydantic schemas for users and auth."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator

SUPPORTED_LANGUAGES = ["en", "ar", "es", "zh", "ru", "fr", "ro", "uk"]
ALLOWED_LANGUAGE_CODES = frozenset(SUPPORTED_LANGUAGES)
# Matches ORM CheckConstraint ck_users_ai_tone
AI_TONE_VALUES = frozenset({"concise", "balanced", "detailed"})


def _validate_language(value: str) -> str:
    if value not in ALLOWED_LANGUAGE_CODES:
        raise ValueError(f"Invalid language. Allowed: {', '.join(sorted(ALLOWED_LANGUAGE_CODES))}")
    return value


def _validate_ai_tone(value: str) -> str:
    if value not in AI_TONE_VALUES:
        raise ValueError("Invalid ai_tone. Allowed: concise, balanced, detailed")
    return value


class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    name: str | None = Field(None, max_length=255)
    company_name: str | None = Field(None, max_length=255)
    language: str = "en"

    _validate_lang = field_validator("language")(_validate_language)


class UserLogin(BaseModel):
    email: EmailStr
    password: str
    remember_me: bool = False


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class TelegramLinkResponse(BaseModel):
    code: str
    bot_url: str


class ChangeInitialPasswordRequest(BaseModel):
    """Used when force_password_change is true: set new email and password."""

    new_email: EmailStr
    new_password: str = Field(min_length=8)


class UserUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    company_name: str | None = Field(None, max_length=255)
    language: str | None = None
    timezone: str | None = Field(None, max_length=50)
    ai_tone: str | None = None
    default_currency: str | None = Field(None, max_length=3)
    avatar_url: str | None = Field(None, max_length=1000000)
    preferences: dict[str, Any] | None = None

    _validate_language_optional = field_validator("language")(_validate_language)
    _validate_ai_tone_optional = field_validator("ai_tone")(_validate_ai_tone)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    persistent: bool = False
    expires_at: str | None = None
    force_password_change: bool | None = None


class UserResponse(BaseModel):
    id: UUID
    email: str
    name: str | None
    company_name: str | None
    plan: str
    trial_ends_at: datetime | None = None
    language: str
    timezone: str = "UTC"
    ai_tone: str = "balanced"
    default_currency: str = "EUR"
    is_superuser: bool = False
    is_active: bool = True
    avatar_url: str | None = None
    last_login_at: datetime | None = None
    created_at: datetime
    telegram_chat_id: int | None = None
    entitlements: dict[str, Any] | None = None

    model_config = {"from_attributes": True}
