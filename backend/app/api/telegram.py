"""Telegram webhook and account linking API."""

import hmac
import logging
import random
import string

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.config import Settings
from app.database import get_db
from app.models.user import User
from app.notifications.telegram_bot import send_message

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/telegram", tags=["telegram"])
settings = Settings()


def _verify_telegram_webhook_secret(request: Request) -> bool:
    """
    Verify X-Telegram-Bot-Api-Secret-Token header.
    When webhook is enabled (bot token set), config validator ensures secret is configured.
    Uses constant-time comparison. Never logs the secret.
    """
    secret = settings.telegram_webhook_secret
    if not secret:
        return False
    received = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if not received:
        return False
    return hmac.compare_digest(secret.encode(), received.encode())


@router.post("/webhook")
async def telegram_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Receive updates from Telegram.
    Called by Telegram servers when users message the bot.
    Validates X-Telegram-Bot-Api-Secret-Token when TELEGRAM_WEBHOOK_SECRET is set.
    """
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

    # Handle /start command
    if text.startswith("/start"):
        await send_message(
            chat_id,
            "👋 <b>Добро пожаловать в Imperecta Bot!</b>\n\n"
            "Для привязки аккаунта:\n"
            "1. Откройте Настройки в приложении\n"
            "2. Нажмите «Получить код привязки»\n"
            "3. Отправьте код сюда\n\n"
            "Команды:\n"
            "/status — статус подключения\n"
            "/help — помощь",
        )
        return {"ok": True}

    # Handle /status command
    if text.startswith("/status"):
        result = await db.execute(
            select(User).where(User.telegram_chat_id == chat_id)
        )
        user = result.scalar_one_or_none()
        if user:
            await send_message(
                chat_id,
                f"✅ <b>Аккаунт привязан</b>\n"
                f"Email: {user.email}\n"
                f"План: {user.plan.value}",
            )
        else:
            await send_message(
                chat_id,
                "❌ Аккаунт не привязан. Отправьте код привязки из Настроек приложения.",
            )
        return {"ok": True}

    # Handle /help command
    if text.startswith("/help"):
        await send_message(
            chat_id,
            "📖 <b>Команды Imperecta Bot</b>\n\n"
            "/start — начало работы\n"
            "/status — статус привязки\n"
            "/help — эта справка\n\n"
            "Отправьте 6-значный код для привязки аккаунта.",
        )
        return {"ok": True}

    # Handle link code (6 alphanumeric characters)
    if len(text.strip()) == 6 and text.strip().isalnum():
        code = text.strip().upper()
        result = await db.execute(
            select(User).where(User.telegram_link_code == code)
        )
        user = result.scalar_one_or_none()

        if user:
            user.telegram_chat_id = chat_id
            user.telegram_link_code = None  # code is one-time use
            # get_db will commit on request completion

            await send_message(
                chat_id,
                f"✅ <b>Аккаунт успешно привязан!</b>\n"
                f"Email: {user.email}\n\n"
                "Теперь вы будете получать алерты об изменении цен прямо в Telegram.",
            )
            logger.info("Telegram linked: user=%s, chat_id=%s", user.email, chat_id)
        else:
            await send_message(
                chat_id,
                "❌ Неверный код. Проверьте код в Настройках приложения и попробуйте снова.",
            )
        return {"ok": True}

    # Unknown message
    await send_message(
        chat_id,
        "Я не понимаю это сообщение. Отправьте /help для списка команд.",
    )
    return {"ok": True}


@router.post("/generate-link-code")
async def generate_link_code(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Generate a 6-character link code for Telegram binding."""
    code = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
    current_user.telegram_link_code = code
    # get_db will commit on request completion

    return {
        "code": code,
        "bot_url": "https://t.me/ImperectaBot",
        "message": f"Отправьте код {code} боту @ImperectaBot в Telegram",
    }


@router.post("/unlink")
async def unlink_telegram(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Unlink Telegram from account."""
    if not current_user.telegram_chat_id:
        raise HTTPException(status_code=400, detail="Telegram not linked")

    current_user.telegram_chat_id = None
    current_user.telegram_link_code = None
    # get_db will commit on request completion

    return {"message": "Telegram отвязан"}


@router.get("/status")
async def telegram_status(
    current_user: User = Depends(get_current_user),
) -> dict:
    """Check if Telegram is linked."""
    return {
        "linked": current_user.telegram_chat_id is not None,
        "chat_id": current_user.telegram_chat_id,
    }
