"""Telegram link/disconnect routes still mounted under /auth/*.

CORE-AUTH1 extracted the auth surface (register/login/refresh/change-initial-password)
to ``app.modules.auth.api``. CORE-USERS1 extracted self-profile (/me) to
``app.modules.users.api``. The two telegram routes remain here pending the
dedicated telegram extraction pass.
"""

import random
import string

from fastapi import APIRouter

from app.common.deps import CurrentUser, DbSession
from app.config import Settings
from app.modules.core.schemas import TelegramLinkResponse

router = APIRouter(prefix="/auth", tags=["auth"])
settings = Settings()


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
