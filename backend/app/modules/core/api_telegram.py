"""Telegram webhook and account linking API."""

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

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/telegram", tags=["telegram"])
settings = Settings()
_telegram_channel = TelegramChannel()


async def _send_html(chat_id: int, html: str) -> bool:
    """Deliver an HTML-formatted bot reply via the Telegram channel.

    The Russian/HTML copy is bot-domain content composed here (the integration
    layer); the channel only delivers - per the notifications strategy
    contract, channels carry no hardcoded language or business semantics.
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
        await _send_html(chat_id, "👋 <b>Добро пожаловать в Imperecta Bot!</b>")
        return {"ok": True}
    if text.startswith("/status"):
        user = (await db.execute(select(User).where(User.telegram_chat_id == chat_id))).scalar_one_or_none()
        if user:
            await _send_html(chat_id, f"✅ <b>Аккаунт привязан</b>\nEmail: {user.email}\nПлан: {user.plan.value}")
        else:
            await _send_html(chat_id, "❌ Аккаунт не привязан. Отправьте код привязки из Настроек приложения.")
        return {"ok": True}
    if text.startswith("/help"):
        await _send_html(chat_id, "📖 <b>Команды Imperecta Bot</b>\n/start\n/status\n/help")
        return {"ok": True}

    if len(text.strip()) == 6 and text.strip().isalnum():
        code = text.strip().upper()
        user = (await db.execute(select(User).where(User.telegram_link_code == code))).scalar_one_or_none()
        if user:
            user.telegram_chat_id = chat_id
            user.telegram_link_code = None
            await _send_html(chat_id, f"✅ <b>Аккаунт успешно привязан!</b>\nEmail: {user.email}")
            logger.info("Telegram linked: user=%s, chat_id=%s", user.email, chat_id)
        else:
            await _send_html(chat_id, "❌ Неверный код.")
        return {"ok": True}

    await _send_html(chat_id, "Я не понимаю это сообщение. Отправьте /help для списка команд.")
    return {"ok": True}


@router.post("/generate-link-code")
async def generate_link_code(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> dict:
    _ = db
    code = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
    current_user.telegram_link_code = code
    return {
        "code": code,
        "bot_url": settings.telegram_bot_url,
        "message": f"Отправьте код {code} в Telegram-бот.",
    }


@router.post("/unlink")
async def unlink_telegram(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> dict:
    _ = db
    if not current_user.telegram_chat_id:
        raise HTTPException(status_code=400, detail="Telegram not linked")
    current_user.telegram_chat_id = None
    current_user.telegram_link_code = None
    return {"message": "Telegram отвязан"}


@router.get("/status")
async def telegram_status(current_user: User = Depends(get_current_user)) -> dict:
    return {"linked": current_user.telegram_chat_id is not None, "chat_id": current_user.telegram_chat_id}
