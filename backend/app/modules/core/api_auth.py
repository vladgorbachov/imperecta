"""Remaining user-profile + telegram-link routes still mounted under /auth/*.

CORE-AUTH1 extracted register/login/refresh/change-initial-password to
``app.modules.auth.api``. /me (GET, PUT) and /auth/telegram-link/disconnect
remain here pending the dedicated users and telegram extraction passes.
"""

import random
import string

from fastapi import APIRouter

from app.common.deps import CurrentUser, DbSession
from app.config import Settings
from app.entitlements import get_entitlements_for_frontend
from app.models.core import User
from app.modules.core.schemas import TelegramLinkResponse, UserResponse, UserUpdate

router = APIRouter(prefix="/auth", tags=["auth"])
settings = Settings()


def _plan_str(plan: object) -> str:
    return plan.value if hasattr(plan, "value") else str(plan)


def _build_user_response(current_user: User) -> UserResponse:
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        name=current_user.name,
        company_name=current_user.company_name,
        plan=_plan_str(current_user.plan),
        trial_ends_at=current_user.trial_ends_at,
        language=current_user.language,
        timezone=getattr(current_user, "timezone", None),
        ai_tone=getattr(current_user, "ai_tone", None),
        default_currency=getattr(current_user, "default_currency", None),
        is_superuser=getattr(current_user, "is_superuser", None),
        is_active=getattr(current_user, "is_active", None),
        created_at=current_user.created_at,
        last_login_at=getattr(current_user, "last_login_at", None),
        telegram_chat_id=current_user.telegram_chat_id,
        avatar_url=getattr(current_user, "avatar_url", None),
        preferences=getattr(current_user, "preferences", None),
        entitlements=get_entitlements_for_frontend(current_user.plan, trial_ends_at=current_user.trial_ends_at),
    )


@router.post("/telegram-link", response_model=TelegramLinkResponse)
async def generate_telegram_link(current_user: CurrentUser, db: DbSession) -> TelegramLinkResponse:
    code = "".join(random.choices(string.digits, k=6))
    current_user.telegram_link_code = code
    await db.flush()
    return TelegramLinkResponse(code=code, bot_url=settings.telegram_bot_url or "")


@router.post("/telegram-disconnect")
async def disconnect_telegram(current_user: CurrentUser, db: DbSession) -> dict:
    current_user.telegram_chat_id = None
    current_user.telegram_link_code = None
    await db.flush()
    return {"ok": True}


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: CurrentUser) -> UserResponse:
    return _build_user_response(current_user)


ALLOWED_USER_UPDATE_FIELDS = frozenset({
    "name",
    "company_name",
    "language",
    "timezone",
    "ai_tone",
    "default_currency",
    "avatar_url",
    "preferences",
})


@router.put("/me", response_model=UserResponse)
async def update_me(data: UserUpdate, current_user: CurrentUser, db: DbSession) -> UserResponse:
    for key, value in data.model_dump(exclude_unset=True).items():
        if key in ALLOWED_USER_UPDATE_FIELDS:
            setattr(current_user, key, None if key == "avatar_url" and value == "" else value)
    await db.flush()
    return _build_user_response(current_user)
