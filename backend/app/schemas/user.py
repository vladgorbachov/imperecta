"""User schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class UserRegister(BaseModel):
    """Schema for user registration."""

    email: EmailStr
    password: str = Field(..., min_length=8)
    name: str
    company_name: str | None = None


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

    class Config:
        from_attributes = True


class UserUpdate(BaseModel):
    """Schema for user profile update."""

    name: str | None = Field(None, max_length=255)
    company_name: str | None = Field(None, max_length=255)
    language: str | None = Field(None, max_length=10)


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
    bot_url: str = "https://t.me/PriceRadarBot"
