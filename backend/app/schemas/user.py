"""User schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator

ALLOWED_LANGUAGE_CODES = frozenset(
    {
        "ru", "uk", "be", "kk", "uz", "ky", "tg", "tk", "az",
        "hy", "ka", "ro", "en", "de", "fr", "es", "it", "pt", "nl", "pl", "cs",
        "sk", "hu", "bg", "hr", "sr", "sl", "mk", "sq", "el", "tr", "fi", "sv",
        "no", "da", "et", "lv", "lt", "ga", "is", "mt", "bs",
    }
)


def _validate_language(v: str) -> str:
    """Validate language code is in allowed list."""
    if v not in ALLOWED_LANGUAGE_CODES:
        raise ValueError(
            f"Invalid language. Allowed: {', '.join(sorted(ALLOWED_LANGUAGE_CODES))}"
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


class UserResponse(BaseModel):
    """Schema for user response."""

    id: UUID
    email: str
    name: str
    company_name: str | None
    plan: str
    trial_ends_at: datetime | None
    language: str
    created_at: datetime
    telegram_chat_id: int | None = None

    class Config:
        from_attributes = True


class UserUpdate(BaseModel):
    """Schema for user profile update."""

    name: str | None = Field(None, max_length=255)
    company_name: str | None = Field(None, max_length=255)
    language: str | None = Field(None, max_length=5)

    @field_validator("language")
    @classmethod
    def validate_language(cls, v: str | None) -> str | None:
        if v is None:
            return None
        return _validate_language(v)


class TokenResponse(BaseModel):
    """Schema for token response."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshTokenRequest(BaseModel):
    """Schema for refresh token request."""

    refresh_token: str


class TelegramLinkResponse(BaseModel):
    """Schema for telegram link code response."""

    code: str
    bot_url: str = "https://t.me/ImperectaBot"
