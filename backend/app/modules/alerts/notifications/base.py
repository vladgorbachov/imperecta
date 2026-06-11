"""Notification channel contract.

Mirrors `app.modules.market_data.providers.base`: a small abstract base class
plus a normalized DTO. Each concrete channel (Telegram, email, ...) is a
strategy implementing :class:`NotificationChannel.send`.

The DTO carries an already-composed message - the CALLER is responsible for
localization, currency formatting, business copy, and severity prefixes. The
channel only delivers. This keeps the delivery core universal: no hardcoded
language, no hardcoded currency, no business semantics.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class NotificationMessage:
    """Caller-composed message handed to a channel for delivery.

    Attributes:
        body: Already-composed, localized message body. Required.
        title: Optional message title. Channels MAY ignore it (e.g. Telegram
            sendMessage has no title field; email subjects use it).
        parse_mode: Channel-specific rendering hint. Telegram supports
            ``"HTML"`` / ``"Markdown"``; email channels ignore it. ``None``
            means plain text.
    """

    body: str
    title: str | None = None
    parse_mode: str | None = None


class NotificationChannel(ABC):
    """Abstract delivery channel.

    Concrete channels implement :meth:`send`. Implementations MUST be:

    * async, side-effect-only (return ``True`` on success / ``False`` on
      missing config or non-OK transport response);
    * stateless w.r.t. business content (the channel does not format
      currency, language, or alert semantics);
    * fail-soft on missing credentials (return ``False``, do not raise -
      this lets the caller decide whether unconfigured channels are an
      error or a no-op).
    """

    @abstractmethod
    async def send(self, recipient: str, message: NotificationMessage) -> bool:
        """Deliver ``message`` to ``recipient``.

        Args:
            recipient: Channel-specific address (Telegram chat id as string,
                email address, etc.).
            message: Caller-composed payload.

        Returns:
            ``True`` if the channel reports successful delivery; ``False`` if
            credentials are missing OR the transport returned a non-OK status.
        """
