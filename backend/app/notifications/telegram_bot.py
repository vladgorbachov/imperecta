"""Telegram bot for alerts and digest via HTTP API (webhook mode)."""

import logging

import httpx

from app.config import Settings

logger = logging.getLogger(__name__)
settings = Settings()


def _api_url() -> str:
    """Telegram API base URL."""
    if not settings.telegram_bot_token:
        return ""
    return f"https://api.telegram.org/bot{settings.telegram_bot_token}"


async def send_message(
    chat_id: int,
    text: str,
    parse_mode: str = "HTML",
) -> bool:
    """Send a message to a Telegram user."""
    if not settings.telegram_bot_token:
        logger.warning("TELEGRAM_BOT_TOKEN not set, skipping message")
        return False

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{_api_url()}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": text,
                    "parse_mode": parse_mode,
                },
            )
            if response.status_code == 200:
                logger.info("Telegram message sent to chat_id=%s", chat_id)
                return True
            logger.error(
                "Telegram API error: %s %s",
                response.status_code,
                response.text,
            )
            return False
    except Exception as e:
        logger.error("Failed to send Telegram message: %s", e)
        return False


async def send_price_alert(
    chat_id: int,
    product_name: str,
    competitor_name: str,
    old_price: float,
    new_price: float,
    currency: str = "RUB",
    marketplace: str = "",
) -> bool:
    """Send a formatted price change alert."""
    change = new_price - old_price
    percent = (change / old_price * 100) if old_price else 0
    direction = "📈" if change > 0 else "📉"
    sign = "+" if change > 0 else ""

    text = (
        f"{direction} <b>Изменение цены</b>\n\n"
        f"<b>Товар:</b> {product_name}\n"
        f"<b>Конкурент:</b> {competitor_name}"
    )
    if marketplace:
        text += f" ({marketplace})"
    text += (
        f"\n<b>Было:</b> {old_price:.0f} {currency}\n"
        f"<b>Стало:</b> {new_price:.0f} {currency}\n"
        f"<b>Изменение:</b> {sign}{change:.0f} {currency} ({sign}{percent:.1f}%)"
    )

    return await send_message(chat_id, text)


async def send_digest(chat_id: int, digest_text: str) -> bool:
    """Send a digest message (may be long, split if needed)."""
    MAX_LENGTH = 4000  # Telegram limit is 4096

    if len(digest_text) <= MAX_LENGTH:
        return await send_message(chat_id, digest_text)

    # Split long digest into chunks
    chunks = []
    while digest_text:
        if len(digest_text) <= MAX_LENGTH:
            chunks.append(digest_text)
            break
        split_at = digest_text.rfind("\n", 0, MAX_LENGTH)
        if split_at == -1:
            split_at = MAX_LENGTH
        chunks.append(digest_text[:split_at])
        digest_text = digest_text[split_at:].lstrip()

    success = True
    for chunk in chunks:
        if not await send_message(chat_id, chunk):
            success = False
    return success


async def send_out_of_stock_alert(
    chat_id: int,
    product_name: str,
    competitor_name: str,
    marketplace: str = "",
) -> bool:
    """Send out-of-stock alert."""
    text = (
        f"⚠️ <b>Нет в наличии</b>\n\n"
        f"<b>Товар:</b> {product_name}\n"
        f"<b>Конкурент:</b> {competitor_name}"
    )
    if marketplace:
        text += f" ({marketplace})"
    text += "\n\nТовар пропал из наличия у конкурента."

    return await send_message(chat_id, text)


async def send_promo_alert(
    chat_id: int,
    product_name: str,
    competitor_name: str,
    promo_label: str,
    marketplace: str = "",
) -> bool:
    """Send new promotion alert."""
    text = (
        f"🏷️ <b>Новая акция</b>\n\n"
        f"<b>Товар:</b> {product_name}\n"
        f"<b>Конкурент:</b> {competitor_name}"
    )
    if marketplace:
        text += f" ({marketplace})"
    text += f"\n<b>Акция:</b> {promo_label}"

    return await send_message(chat_id, text)
