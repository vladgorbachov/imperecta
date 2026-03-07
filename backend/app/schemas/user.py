"""User schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator

# UN official languages only
SUPPORTED_LANGUAGES = ["en", "ar", "es", "zh", "ru", "fr"]
ALLOWED_LANGUAGE_CODES = frozenset(SUPPORTED_LANGUAGES)

AI_TONE_VALUES = frozenset({"conservative", "balanced", "aggressive"})


def _validate_language(v: str) -> str:
    """Validate language code is in allowed list."""
    if v not in ALLOWED_LANGUAGE_CODES:
        raise ValueError(
            f"Invalid language. Allowed: {', '.join(sorted(ALLOWED_LANGUAGE_CODES))}"
        )
    return v


def _validate_ai_tone(v: str) -> str:
    """Validate ai_tone is in allowed values."""
    if v not in AI_TONE_VALUES:
        raise ValueError(
            f"Invalid ai_tone. Allowed: {', '.join(sorted(AI_TONE_VALUES))}"
        )
    return v


class UserRegister(BaseModel):
    """Schema for user registration."""

    email: EmailStr
    password: str = Field(..., min_length=8)
    name: str
    company_name: str | None = None
    language: str = "en"

    @field_validator("language")
    @classmethod
    def validate_language(cls, v: str) -> str:
        return _validate_language(v)


class UserLogin(BaseModel):
    """Schema for user login."""

    email: EmailStr
    password: str
    remember_me: bool = False


class UserResponse(BaseModel):
    """Schema for user response."""

    id: UUID
    email: str
    name: str
    company_name: str | None
    plan: str
    trial_ends_at: datetime | None
    language: str
    ai_tone: str = "balanced"
    created_at: datetime
    telegram_chat_id: int | None = None
    avatar_url: str | None = None

    class Config:
        from_attributes = True


class UserUpdate(BaseModel):
    """Schema for user profile update."""

    name: str | None = Field(None, max_length=255)
    company_name: str | None = Field(None, max_length=255)
    language: str | None = Field(None, max_length=5)
    ai_tone: str | None = Field(None, max_length=20)
    avatar_url: str | None = Field(None, max_length=500_000)

    @field_validator("language")
    @classmethod
    def validate_language(cls, v: str | None) -> str | None:
        if v is None:
            return None
        return _validate_language(v)

    @field_validator("ai_tone")
    @classmethod
    def validate_ai_tone(cls, v: str | None) -> str | None:
        if v is None:
            return None
        return _validate_ai_tone(v)


class TokenResponse(BaseModel):
    """Schema for token response."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    persistent: bool = False
    expires_at: str | None = None
    force_password_change: bool | None = None


class ChangeInitialPasswordRequest(BaseModel):
    """Schema for forced password change (superuser first login)."""

    new_email: EmailStr
    new_password: str = Field(..., min_length=8)


class RefreshTokenRequest(BaseModel):
    """Schema for refresh token request."""

    refresh_token: str


class TelegramLinkResponse(BaseModel):
    """Schema for telegram link code response."""

    code: str
    bot_url: str = "https://t.me/ImperectaBot"
