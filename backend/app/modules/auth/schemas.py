"""Auth request/response schemas.

Owns only the auth-specific surface (register/login/refresh/change-initial-password).
Profile schemas (UserResponse, UserUpdate, TelegramLinkResponse) still live in
``app.modules.core.schemas`` and will move with the users + telegram passes.
"""

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.common.validation import validate_language


class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    name: str | None = Field(None, max_length=255)
    company_name: str | None = Field(None, max_length=255)
    language: str

    _validate_lang = field_validator("language")(validate_language)


class UserLogin(BaseModel):
    email: EmailStr
    password: str
    remember_me: bool = False


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class ChangeInitialPasswordRequest(BaseModel):
    """Used when force_password_change is true: set new email and password."""

    new_email: EmailStr
    new_password: str = Field(min_length=8)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    persistent: bool = False
    expires_at: str | None = None
    force_password_change: bool | None = None
