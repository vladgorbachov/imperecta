"""Authentication endpoints."""

import random
import string
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from jose import JWTError
from sqlalchemy import select

from app.common.deps import CurrentUser, DbSession
from app.entitlements import get_entitlements_for_frontend
from app.modules.alerts.notifications import BOT_URL
from app.modules.core.auth.service import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.modules.core.models import User, UserPlan
from app.modules.core.schemas import (
    ChangeInitialPasswordRequest,
    RefreshTokenRequest,
    TelegramLinkResponse,
    TokenResponse,
    UserLogin,
    UserRegister,
    UserResponse,
    UserUpdate,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _create_tokens(user_id: UUID, force_password_change: bool | None = None, persistent: bool = False) -> TokenResponse:
    refresh_token, expire = create_refresh_token(user_id, persistent=persistent)
    response = TokenResponse(
        access_token=create_access_token(user_id),
        refresh_token=refresh_token,
        persistent=persistent,
        expires_at=expire.isoformat(),
    )
    if force_password_change is not None:
        response.force_password_change = force_password_change
    return response


def _build_user_response(current_user: User) -> UserResponse:
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        name=current_user.name,
        company_name=current_user.company_name,
        plan=current_user.plan.value,
        trial_ends_at=current_user.trial_ends_at,
        language=current_user.language,
        ai_tone=getattr(current_user, "ai_tone", "balanced"),
        is_superuser=getattr(current_user, "is_superuser", False),
        created_at=current_user.created_at,
        telegram_chat_id=current_user.telegram_chat_id,
        avatar_url=getattr(current_user, "avatar_url", None),
        entitlements=get_entitlements_for_frontend(current_user.plan, trial_ends_at=current_user.trial_ends_at),
    )


@router.post("/register", response_model=TokenResponse)
async def register(data: UserRegister, db: DbSession) -> TokenResponse:
    existing = (await db.execute(select(User).where(User.email == data.email))).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    user = User(
        email=data.email,
        password_hash=hash_password(data.password),
        name=data.name,
        company_name=data.company_name,
        plan=UserPlan.trial,
        trial_ends_at=datetime.now(timezone.utc) + timedelta(days=14),
        language=data.language,
    )
    db.add(user)
    await db.flush()
    return _create_tokens(user.id)


@router.post("/login", response_model=TokenResponse)
async def login(data: UserLogin, db: DbSession) -> TokenResponse:
    user = (await db.execute(select(User).where(User.email == data.email))).scalar_one_or_none()
    if user is None or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    user.last_login_at = datetime.now(timezone.utc)
    await db.flush()
    force_change = user.force_password_change if user.force_password_change else None
    return _create_tokens(user.id, force_password_change=force_change, persistent=data.remember_me)


@router.post("/change-initial-password", response_model=TokenResponse)
async def change_initial_password(data: ChangeInitialPasswordRequest, current_user: CurrentUser, db: DbSession) -> TokenResponse:
    if not current_user.force_password_change:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Initial password change not required")
    existing = (await db.execute(select(User).where(User.email == data.new_email))).scalar_one_or_none()
    if existing is not None and existing.id != current_user.id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already in use")
    current_user.email = data.new_email
    current_user.password_hash = hash_password(data.new_password)
    current_user.force_password_change = False
    await db.flush()
    return _create_tokens(current_user.id)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(data: RefreshTokenRequest, db: DbSession) -> TokenResponse:
    try:
        payload = decode_token(data.refresh_token)
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token")
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")
    user_id_str = payload.get("sub")
    if not user_id_str:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")
    try:
        user_id = UUID(user_id_str)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    persistent = payload.get("persistent") is True
    refresh_token, expire = create_refresh_token(user_id, persistent=persistent)
    return TokenResponse(
        access_token=create_access_token(user_id),
        refresh_token=refresh_token,
        token_type="bearer",
        persistent=persistent,
        expires_at=expire.isoformat(),
    )


@router.post("/telegram-link", response_model=TelegramLinkResponse)
async def generate_telegram_link(current_user: CurrentUser, db: DbSession) -> TelegramLinkResponse:
    code = "".join(random.choices(string.digits, k=6))
    current_user.telegram_link_code = code
    await db.flush()
    return TelegramLinkResponse(code=code, bot_url=BOT_URL)


@router.post("/telegram-disconnect")
async def disconnect_telegram(current_user: CurrentUser, db: DbSession) -> dict:
    current_user.telegram_chat_id = None
    current_user.telegram_link_code = None
    await db.flush()
    return {"ok": True}


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: CurrentUser) -> UserResponse:
    return _build_user_response(current_user)


ALLOWED_USER_UPDATE_FIELDS = frozenset({"name", "company_name", "language", "ai_tone", "avatar_url"})


@router.put("/me", response_model=UserResponse)
async def update_me(data: UserUpdate, current_user: CurrentUser, db: DbSession) -> UserResponse:
    for key, value in data.model_dump(exclude_unset=True).items():
        if key in ALLOWED_USER_UPDATE_FIELDS:
            setattr(current_user, key, None if key == "avatar_url" and value == "" else value)
    await db.flush()
    return _build_user_response(current_user)


@router.delete("/avatar")
async def delete_avatar(current_user: CurrentUser, db: DbSession) -> dict:
    current_user.avatar_url = None
    await db.flush()
    return {"message": "Avatar removed"}
