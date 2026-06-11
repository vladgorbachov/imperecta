"""User profile + admin-user-CRUD schemas."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.common.validation import validate_ai_tone, validate_language


class UserUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    company_name: str | None = Field(None, max_length=255)
    language: str | None = None
    timezone: str | None = Field(None, max_length=50)
    ai_tone: str | None = None
    default_currency: str | None = Field(None, max_length=3)
    avatar_url: str | None = Field(None, max_length=1000000)
    preferences: dict[str, Any] | None = None

    _validate_language_optional = field_validator("language")(validate_language)
    _validate_ai_tone_optional = field_validator("ai_tone")(validate_ai_tone)


class UserResponse(BaseModel):
    id: UUID
    email: str
    name: str | None
    company_name: str | None
    plan: str
    trial_ends_at: datetime | None = None
    language: str
    timezone: str | None = None
    ai_tone: str | None = None
    default_currency: str | None = None
    is_superuser: bool | None = None
    is_active: bool | None = None
    avatar_url: str | None = None
    last_login_at: datetime | None = None
    created_at: datetime
    telegram_chat_id: int | None = None
    preferences: dict[str, Any] | None = None
    entitlements: dict[str, Any] | None = None

    model_config = {"from_attributes": True}


class AdminUserCreateRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str | None = Field(default=None, max_length=100)
    company_name: str | None = Field(default=None, max_length=200)
    plan: str
    language: str
    timezone: str | None = Field(default="UTC", max_length=50)
    is_active: bool = True
    is_superuser: bool = False


class AdminUserUpdateRequest(BaseModel):
    email: EmailStr | None = None
    name: str | None = Field(default=None, max_length=100)
    company_name: str | None = Field(default=None, max_length=200)
    plan: str | None = None
    language: str | None = None
    timezone: str | None = Field(default=None, max_length=50)
    is_active: bool | None = None
    is_superuser: bool | None = None


class AdminUserStatusRequest(BaseModel):
    is_active: bool


class AdminUserRoleRequest(BaseModel):
    is_superuser: bool


class AdminUserPasswordResetRequest(BaseModel):
    new_password: str = Field(min_length=8, max_length=128)
    force_password_change: bool = True
