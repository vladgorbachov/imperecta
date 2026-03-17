"""Notifications for email and Telegram."""

import logging
import re
from uuid import UUID

import httpx
import resend

from app.config import Settings

logger = logging.getLogger(__name__)
settings = Settings()
BOT_URL = "https://t.me/ImperectaBot"


def _md_to_html(md: str) -> str:
    html = md.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    html = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html)
    html = re.sub(r"\*(.+?)\*", r"<em>\1</em>", html)
    html = re.sub(r"\n\n", "</p><p>", html)
    html = re.sub(r"\n", "<br>", html)
    return f"<p>{html}</p>"


def _api_url() -> str:
    if not settings.telegram_bot_token:
        return ""
    return f"https://api.telegram.org/bot{settings.telegram_bot_token}"


async def send_message(chat_id: int, text: str, parse_mode: str = "HTML") -> bool:
    if not settings.telegram_bot_token:
        return False
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(f"{_api_url()}/sendMessage", json={"chat_id": chat_id, "text": text, "parse_mode": parse_mode})
        return response.status_code == 200


async def send_price_alert(chat_id: int, product_name: str, competitor_name: str, old_price: float, new_price: float, currency: str = "RUB", marketplace: str = "") -> bool:
    change = new_price - old_price
    percent = (change / old_price * 100) if old_price else 0
    direction = "📈" if change > 0 else "📉"
    sign = "+" if change > 0 else ""
    text = (
        f"{direction} <b>Изменение цены</b>\n\n"
        f"<b>Товар:</b> {product_name}\n"
        f"<b>Конкурент:</b> {competitor_name}{f' ({marketplace})' if marketplace else ''}\n"
        f"<b>Было:</b> {old_price:.0f} {currency}\n"
        f"<b>Стало:</b> {new_price:.0f} {currency}\n"
        f"<b>Изменение:</b> {sign}{change:.0f} {currency} ({sign}{percent:.1f}%)"
    )
    return await send_message(chat_id, text)


async def send_out_of_stock_alert(chat_id: int, product_name: str, competitor_name: str, marketplace: str = "") -> bool:
    text = f"⚠️ <b>Нет в наличии</b>\n\n<b>Товар:</b> {product_name}\n<b>Конкурент:</b> {competitor_name}{f' ({marketplace})' if marketplace else ''}"
    return await send_message(chat_id, text)


async def send_promo_alert(chat_id: int, product_name: str, competitor_name: str, promo_label: str, marketplace: str = "") -> bool:
    text = f"🏷️ <b>Новая акция</b>\n\n<b>Товар:</b> {product_name}\n<b>Конкурент:</b> {competitor_name}{f' ({marketplace})' if marketplace else ''}\n<b>Акция:</b> {promo_label}"
    return await send_message(chat_id, text)


async def send_digest(chat_id: int, digest_text: str) -> bool:
    return await send_message(chat_id, digest_text[:4000])


async def send_alert_email(to: str, subject: str, body_html: str) -> None:
    if not settings.resend_api_key:
        return
    resend.api_key = settings.resend_api_key
    resend.Emails.send({"from": settings.email_from, "to": [to], "subject": subject, "html": body_html})


async def send_digest_email(to: str, digest_md: str) -> None:
    await send_alert_email(to, "Imperecta — Еженедельный дайджест", _md_to_html(digest_md))


def send_alert_email_to_user(user_id: UUID, message: str) -> None:
    import asyncio

    from sqlalchemy import select

    from app.database import async_session_maker
    from app.models import User

    async def _do():
        async with async_session_maker() as session:
            user = (await session.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
            if user:
                await send_alert_email(user.email, "Imperecta: Уведомление", f"<p>{message}</p>")

    asyncio.run(_do())


def send_digest_email_to_user(user_id: UUID, subject: str, content_md: str) -> None:
    _ = subject
    import asyncio

    from sqlalchemy import select

    from app.database import async_session_maker
    from app.models import User

    async def _do():
        async with async_session_maker() as session:
            user = (await session.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
            if user:
                await send_digest_email(user.email, content_md)

    asyncio.run(_do())
