"""User schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator

SUPPORTED_LANGUAGES = ["en", "ar", "es", "zh", "ru", "fr", "ro", "uk"]
ALLOWED_LANGUAGE_CODES = frozenset(SUPPORTED_LANGUAGES)
AI_TONE_VALUES = frozenset({"conservative", "balanced", "aggressive"})


def _validate_language(value: str) -> str:
    if value not in ALLOWED_LANGUAGE_CODES:
        raise ValueError(f"Invalid language. Allowed: {', '.join(sorted(ALLOWED_LANGUAGE_CODES))}")
    return value


def _validate_ai_tone(value: str) -> str:
    if value not in AI_TONE_VALUES:
        raise ValueError("Invalid ai_tone. Allowed: conservative, balanced, aggressive")
    return value


class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)
    name: str = Field(..., min_length=1, max_length=255)
    company_name: str | None = Field(None, max_length=255)
    language: str = Field(default="en")

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
    new_email: EmailStr
    new_password: str = Field(..., min_length=8)


class UserUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    company_name: str | None = Field(None, max_length=255)
    language: str | None = None
    ai_tone: str | None = None
    avatar_url: str | None = Field(None, max_length=1000000)

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
    email: EmailStr
    name: str
    company_name: str | None
    plan: str
    trial_ends_at: datetime | None
    language: str
    ai_tone: str = "balanced"
    is_superuser: bool = False
    created_at: datetime
    telegram_chat_id: int | None = None
    avatar_url: str | None = None
    entitlements: dict | None = None
