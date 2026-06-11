"""Telegram webhook + account-linking API.

CORE-TG1 lifted this out of ``app.modules.core.api_telegram`` (last resident
of core), dropped the duplicated /auth/telegram-link|disconnect surface,
moved every bot reply string into the English module constants below, and
typed the link/unlink/status responses.

Bot replies are English pending per-user-language localization keyed off
``User.language`` (future i18n task; one-line note, not scattered TODOs).
"""

from __future__ import annotations

import hmac
import logging
import random
import string

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.deps import get_current_user
from app.config import Settings
from app.database import get_db
from app.models.core import User
from app.modules.alerts.notifications import NotificationMessage, TelegramChannel
from app.modules.telegram.schemas import (
    TelegramLinkCodeResponse,
    TelegramStatusResponse,
    TelegramUnlinkResponse,
)

logger = logging.getLogger(__name__)

# Length of the 6-character ALNUM link code generated for the bot. The webhook
# matches `text.strip().isalnum() and len == LINK_CODE_LENGTH`, so the two
# numbers stay in lockstep.
LINK_CODE_LENGTH: int = 6
LINK_CODE_ALPHABET: str = string.ascii_uppercase + string.digits

# ---- Bot reply strings (English; HTML formatting preserved) -----------------

TG_WELCOME: str = "\U0001f44b <b>Welcome to Imperecta Bot!</b>"
TG_LINKED_FMT: str = (
    "\u2705 <b>Account linked</b>\nEmail: {email}\nPlan: {plan}"
)
TG_NOT_LINKED: str = (
    "\u274c Account not linked. Send the linking code from the app Settings."
)
TG_HELP: str = (
    "\U0001f4d6 <b>Imperecta Bot commands</b>\n/start\n/status\n/help"
)
TG_LINK_SUCCESS_FMT: str = (
    "\u2705 <b>Account linked successfully!</b>\nEmail: {email}"
)
TG_BAD_CODE: str = "\u274c Invalid code."
TG_UNKNOWN: str = (
    "I don't understand this message. Send /help for the command list."
)


router = APIRouter(prefix="/telegram", tags=["telegram"])
settings = Settings()
_telegram_channel = TelegramChannel()


async def _send_html(chat_id: int, html: str) -> bool:
    """Deliver an HTML-formatted bot reply via the Telegram channel.

    Bot-domain content is composed here (the integration layer); the channel
    only delivers - per the notifications strategy contract, channels carry
    no hardcoded language or business semantics.
    """
    return await _telegram_channel.send(
        str(chat_id),
        NotificationMessage(body=html, parse_mode="HTML"),
    )


def _verify_telegram_webhook_secret(request: Request) -> bool:
    """Verify X-Telegram-Bot-Api-Secret-Token header."""
    secret = settings.telegram_webhook_secret
    if not secret:
        return False
    received = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if not received:
        return False
    return hmac.compare_digest(secret.encode(), received.encode())


@router.post("/webhook")
async def telegram_webhook(request: Request, db: AsyncSession = Depends(get_db)) -> dict:
    if not _verify_telegram_webhook_secret(request):
        logger.warning("Telegram webhook rejected: invalid or missing secret header")
        raise HTTPException(status_code=403, detail="Invalid webhook secret")
    try:
        data = await request.json()
    except Exception:
        return {"ok": True}

    message = data.get("message", {})
    text = message.get("text", "")
    chat_id = message.get("chat", {}).get("id")
    if not chat_id:
        return {"ok": True}

    if text.startswith("/start"):
        await _send_html(chat_id, TG_WELCOME)
        return {"ok": True}
    if text.startswith("/status"):
        user = (
            await db.execute(select(User).where(User.telegram_chat_id == chat_id))
        ).scalar_one_or_none()
        if user:
            await _send_html(
                chat_id,
                TG_LINKED_FMT.format(email=user.email, plan=user.plan.value),
            )
        else:
            await _send_html(chat_id, TG_NOT_LINKED)
        return {"ok": True}
    if text.startswith("/help"):
        await _send_html(chat_id, TG_HELP)
        return {"ok": True}

    candidate = text.strip()
    if len(candidate) == LINK_CODE_LENGTH and candidate.isalnum():
        code = candidate.upper()
        user = (
            await db.execute(select(User).where(User.telegram_link_code == code))
        ).scalar_one_or_none()
        if user:
            user.telegram_chat_id = chat_id
            user.telegram_link_code = None
            await db.flush()
            await _send_html(
                chat_id,
                TG_LINK_SUCCESS_FMT.format(email=user.email),
            )
            logger.info("Telegram linked: user=%s, chat_id=%s", user.email, chat_id)
        else:
            await _send_html(chat_id, TG_BAD_CODE)
        return {"ok": True}

    await _send_html(chat_id, TG_UNKNOWN)
    return {"ok": True}


@router.post("/generate-link-code", response_model=TelegramLinkCodeResponse)
async def generate_link_code(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TelegramLinkCodeResponse:
    code = "".join(random.choices(LINK_CODE_ALPHABET, k=LINK_CODE_LENGTH))
    current_user.telegram_link_code = code
    await db.flush()
    return TelegramLinkCodeResponse(
        code=code,
        bot_url=settings.telegram_bot_url or "",
    )


@router.post("/unlink", response_model=TelegramUnlinkResponse)
async def unlink_telegram(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TelegramUnlinkResponse:
    if not current_user.telegram_chat_id:
        raise HTTPException(status_code=400, detail="Telegram not linked")
    current_user.telegram_chat_id = None
    current_user.telegram_link_code = None
    await db.flush()
    return TelegramUnlinkResponse(unlinked=True)


@router.get("/status", response_model=TelegramStatusResponse)
async def telegram_status(
    current_user: User = Depends(get_current_user),
) -> TelegramStatusResponse:
    return TelegramStatusResponse(
        linked=current_user.telegram_chat_id is not None,
        chat_id=current_user.telegram_chat_id,
    )
