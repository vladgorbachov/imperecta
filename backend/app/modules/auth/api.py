"""Authentication endpoints: register, login, refresh, change-initial-password.

CORE-AUTH1 extracted these from ``app.modules.core.api_auth``; paths and
behavior are preserved verbatim (the frontend depends on them).
"""

from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from jose import JWTError
from sqlalchemy import select

from app.common.deps import CurrentUser, DbSession
from app.entitlements.plan import UserPlan
from app.models.core import User
from app.modules.auth.schemas import (
    ChangeInitialPasswordRequest,
    RefreshTokenRequest,
    TokenResponse,
    UserLogin,
    UserRegister,
)
from app.modules.auth.service import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)

# Trial-plan grace period applied at registration (mirrors the entitlements roadmap).
TRIAL_DURATION_DAYS: int = 14

router = APIRouter(prefix="/auth", tags=["auth"])


def _create_tokens(
    user_id: UUID,
    force_password_change: bool | None = None,
    persistent: bool = False,
) -> TokenResponse:
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
        plan=UserPlan.trial.value,
        trial_ends_at=datetime.now(timezone.utc) + timedelta(days=TRIAL_DURATION_DAYS),
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
async def change_initial_password(
    data: ChangeInitialPasswordRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> TokenResponse:
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
