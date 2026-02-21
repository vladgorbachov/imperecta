"""Telegram bot for alerts and digest."""

import asyncio
import logging
import re
from uuid import UUID

from sqlalchemy import select
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from app.config import Settings
from app.database import async_session_maker
from app.models import CompetitorProduct, Digest, Product, User

logger = logging.getLogger(__name__)
settings = Settings()
BOT_URL = "https://t.me/PriceRadarBot"
MAX_MESSAGE_LENGTH = 4096
RETRY_COUNT = 2


def _md_to_telegram_html(text: str) -> str:
    """Convert markdown to Telegram HTML (bold, italic)."""
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"\*(.+?)\*", r"<i>\1</i>", text)
    text = re.sub(r"__(.+?)__", r"<b>\1</b>", text)
    text = re.sub(r"_(.+?)_", r"<i>\1</i>", text)
    text = re.sub(r"^### (.+)$", r"<b>\1</b>", text, flags=re.MULTILINE)
    text = re.sub(r"^## (.+)$", r"<b>\1</b>", text, flags=re.MULTILINE)
    text = re.sub(r"^# (.+)$", r"<b>\1</b>", text, flags=re.MULTILINE)
    return text


async def _start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command."""
    await update.message.reply_text(
        "Привет! Я бот PriceRadar — мониторинг цен конкурентов.\n\n"
        "Введите код привязки из личного кабинета PriceRadar."
    )


async def _text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle text message: check telegram_link_code and link account."""
    text = (update.message.text or "").strip()
    if not text:
        return

    chat_id = update.effective_chat.id if update.effective_chat else None
    if not chat_id:
        return

    async with async_session_maker() as session:
        result = await session.execute(select(User).where(User.telegram_link_code == text))
        user = result.scalar_one_or_none()

        if user:
            user.telegram_chat_id = chat_id
            user.telegram_link_code = None
            await session.commit()
            await update.message.reply_text("Аккаунт привязан!")
        else:
            await update.message.reply_text("Код не найден. Проверьте код в личном кабинете.")


async def _status_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /status: show tracked products count and last price."""
    chat_id = update.effective_chat.id if update.effective_chat else None
    if not chat_id:
        return

    async with async_session_maker() as session:
        result = await session.execute(select(User).where(User.telegram_chat_id == chat_id))
        user = result.scalar_one_or_none()
        if not user:
            await update.message.reply_text("Сначала привяжите аккаунт. Введите код из личного кабинета.")
            return

        count_result = await session.execute(
            select(CompetitorProduct)
            .join(Product, CompetitorProduct.product_id == Product.id)
            .where(Product.user_id == user.id, CompetitorProduct.is_active.is_(True))
        )
        cps = count_result.scalars().all()
        total = len(cps)

        last_price_msg = ""
        if cps:
            cp = cps[0]
            if cp.last_price is not None:
                last_price_msg = f"\nПоследняя цена: {cp.last_price} ₽"

        await update.message.reply_text(
            f"Отслеживаемых товаров: {total}{last_price_msg}"
        )


async def _digest_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /digest: send latest digest."""
    chat_id = update.effective_chat.id if update.effective_chat else None
    if not chat_id:
        return

    async with async_session_maker() as session:
        result = await session.execute(select(User).where(User.telegram_chat_id == chat_id))
        user = result.scalar_one_or_none()
        if not user:
            await update.message.reply_text("Сначала привяжите аккаунт.")
            return

        digest_result = await session.execute(
            select(Digest)
            .where(Digest.user_id == user.id)
            .order_by(Digest.created_at.desc())
            .limit(1)
        )
        digest = digest_result.scalar_one_or_none()
        if not digest:
            await update.message.reply_text("Дайджестов пока нет.")
            return

        await send_telegram_digest(chat_id, digest.content_md)


async def send_telegram_alert(chat_id: int, message: str) -> None:
    """Send formatted alert message (HTML). Retry 2 times on error."""
    if not settings.telegram_bot_token:
        logger.warning("TELEGRAM_BOT_TOKEN not set")
        return

    html = f"<b>PriceRadar</b>\n\n{message.replace('<', '&lt;').replace('>', '&gt;')}"
    last_error = None
    for attempt in range(RETRY_COUNT + 1):
        try:
            from telegram import Bot

            bot = Bot(token=settings.telegram_bot_token)
            await bot.send_message(
                chat_id=chat_id,
                text=html,
                parse_mode="HTML",
            )
            return
        except Exception as e:
            last_error = e
            if attempt < RETRY_COUNT:
                await asyncio.sleep(1)
    logger.warning("Telegram alert send failed after retries: %s", last_error)


async def send_telegram_digest(chat_id: int, digest_md: str) -> None:
    """Convert markdown to Telegram HTML, split if > 4096 chars."""
    if not settings.telegram_bot_token:
        logger.warning("TELEGRAM_BOT_TOKEN not set")
        return

    html = _md_to_telegram_html(digest_md)
    parts = []
    while len(html) > MAX_MESSAGE_LENGTH:
        parts.append(html[:MAX_MESSAGE_LENGTH])
        html = html[MAX_MESSAGE_LENGTH:]
    if html:
        parts.append(html)

    from telegram import Bot

    bot = Bot(token=settings.telegram_bot_token)
    for part in parts:
        try:
            await bot.send_message(chat_id=chat_id, text=part, parse_mode="HTML")
        except Exception as e:
            logger.warning("Telegram digest send failed: %s", e)
            break


def send_alert_telegram(user_id: UUID, message: str) -> None:
    """Sync wrapper: fetch chat_id and send alert. Used by Celery."""
    import asyncio

    async def _do():
        async with async_session_maker() as session:
            result = await session.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()
            if user and user.telegram_chat_id:
                await send_telegram_alert(user.telegram_chat_id, message)

    asyncio.run(_do())


def send_digest_telegram(user_id: UUID, content: str) -> None:
    """Sync wrapper for Celery."""
    import asyncio

    async def _do():
        async with async_session_maker() as session:
            result = await session.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()
            if user and user.telegram_chat_id:
                await send_telegram_digest(user.telegram_chat_id, content)

    asyncio.run(_do())


def run_bot() -> None:
    """Run Telegram bot (polling). Call from separate process."""
    if not settings.telegram_bot_token:
        raise ValueError("TELEGRAM_BOT_TOKEN required")

    app = Application.builder().token(settings.telegram_bot_token).build()
    app.add_handler(CommandHandler("start", _start_handler))
    app.add_handler(CommandHandler("status", _status_handler))
    app.add_handler(CommandHandler("digest", _digest_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, _text_handler))
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    run_bot()
