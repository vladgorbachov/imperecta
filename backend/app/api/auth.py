"""Authentication endpoints."""

import random
import string
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from jose import JWTError
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.models import User
from app.models.user import UserPlan
from app.notifications.telegram_bot import BOT_URL
from app.schemas.user import (
    RefreshTokenRequest,
    TelegramLinkResponse,
    TokenResponse,
    UserLogin,
    UserRegister,
    UserResponse,
    UserUpdate,
)
from app.services.auth_service import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)

router = APIRouter()


def _create_tokens(user_id: UUID) -> TokenResponse:
    """Create access and refresh tokens for user."""
    return TokenResponse(
        access_token=create_access_token(user_id),
        refresh_token=create_refresh_token(user_id),
    )


@router.post("/register", response_model=TokenResponse)
async def register(
    data: UserRegister,
    db: DbSession,
) -> TokenResponse:
    """Create new user with trial plan, return tokens."""
    result = await db.execute(select(User).where(User.email == data.email))
    existing = result.scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    trial_ends_at = datetime.now(timezone.utc) + timedelta(days=14)
    user = User(
        email=data.email,
        password_hash=hash_password(data.password),
        name=data.name,
        company_name=data.company_name,
        plan=UserPlan.trial,
        trial_ends_at=trial_ends_at,
        language=data.language,
    )
    db.add(user)
    await db.flush()

    return _create_tokens(user.id)


@router.post("/login", response_model=TokenResponse)
async def login(
    data: UserLogin,
    db: DbSession,
) -> TokenResponse:
    """Verify credentials, return tokens."""
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    return _create_tokens(user.id)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    data: RefreshTokenRequest,
    db: DbSession,
) -> TokenResponse:
    """Return new access token from refresh token."""
    try:
        payload = decode_token(data.refresh_token)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )

    user_id_str = payload.get("sub")
    if not user_id_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    try:
        user_id = UUID(user_id_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    return TokenResponse(
        access_token=create_access_token(user_id),
        refresh_token=data.refresh_token,
        token_type="bearer",
    )


@router.post("/telegram-link", response_model=TelegramLinkResponse)
async def generate_telegram_link(
    current_user: CurrentUser,
    db: DbSession,
) -> TelegramLinkResponse:
    """Generate 6-digit link code, save to user, return code and bot URL."""
    code = "".join(random.choices(string.digits, k=6))
    current_user.telegram_link_code = code
    await db.flush()
    return TelegramLinkResponse(code=code, bot_url=BOT_URL)


@router.post("/telegram-disconnect")
async def disconnect_telegram(
    current_user: CurrentUser,
    db: DbSession,
) -> dict:
    """Disconnect Telegram from user account."""
    current_user.telegram_chat_id = None
    current_user.telegram_link_code = None
    await db.flush()
    return {"ok": True}


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: CurrentUser) -> UserResponse:
    """Return current authenticated user."""
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        name=current_user.name,
        company_name=current_user.company_name,
        plan=current_user.plan.value,
        trial_ends_at=current_user.trial_ends_at,
        language=current_user.language,
        created_at=current_user.created_at,
        telegram_chat_id=current_user.telegram_chat_id,
    )


@router.put("/me", response_model=UserResponse)
async def update_me(
    data: UserUpdate,
    current_user: CurrentUser,
    db: DbSession,
) -> UserResponse:
    """Update current user profile."""
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(current_user, key, value)
    await db.flush()
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        name=current_user.name,
        company_name=current_user.company_name,
        plan=current_user.plan.value,
        trial_ends_at=current_user.trial_ends_at,
        language=current_user.language,
        created_at=current_user.created_at,
        telegram_chat_id=current_user.telegram_chat_id,
    )
