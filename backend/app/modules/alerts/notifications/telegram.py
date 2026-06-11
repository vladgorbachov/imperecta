"""Telegram channel strategy.

Delivers caller-composed messages via the Telegram Bot API ``sendMessage``
endpoint. The channel itself contains zero business copy - the caller
provides a fully-rendered ``NotificationMessage.body``.
"""

import logging

import httpx

from app.config import Settings
from app.modules.alerts.notifications.base import NotificationChannel, NotificationMessage

logger = logging.getLogger(__name__)
settings = Settings()

_TELEGRAM_API_BASE = "https://api.telegram.org"
_TIMEOUT_SECONDS = 10.0


class TelegramChannel(NotificationChannel):
    """Send messages via Telegram Bot API.

    Reads bot token from :class:`app.config.Settings`. If the token is unset,
    :meth:`send` returns ``False`` instead of raising - this keeps callers
    safe in environments where Telegram is intentionally not configured.
    """

    async def send(self, recipient: str, message: NotificationMessage) -> bool:
        """Deliver ``message`` to a Telegram chat.

        Args:
            recipient: Telegram chat id as a string. Coerced to int per the
                Bot API contract.
            message: Caller-composed payload. ``parse_mode`` (e.g. ``"HTML"``)
                is forwarded verbatim; ``title`` is ignored because the Bot
                API ``sendMessage`` shape has no separate title field.

        Returns:
            ``True`` when Telegram returns HTTP 200; ``False`` when the bot
            token is unset, the recipient is not a valid integer chat id, or
            the API responds non-200.
        """
        token = settings.telegram_bot_token
        if not token:
            return False

        try:
            chat_id = int(recipient)
        except (TypeError, ValueError):
            logger.warning("Telegram recipient is not a numeric chat id: %r", recipient)
            return False

        payload: dict[str, object] = {"chat_id": chat_id, "text": message.body}
        if message.parse_mode:
            payload["parse_mode"] = message.parse_mode

        url = f"{_TELEGRAM_API_BASE}/bot{token}/sendMessage"
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
                response = await client.post(url, json=payload)
        except httpx.HTTPError as exc:
            logger.warning("Telegram delivery failed for chat %s: %s", chat_id, exc)
            return False

        if response.status_code != 200:
            logger.warning(
                "Telegram non-200 for chat %s: status=%s body=%s",
                chat_id,
                response.status_code,
                response.text[:200],
            )
            return False
        return True
