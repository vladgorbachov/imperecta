"""Notification delivery infrastructure (channel strategies).

Exposes the channel contract plus concrete strategies. Mirrors the
``market_data.providers`` pattern: callers import the abstract
:class:`NotificationChannel` for typing / DI, and a concrete channel
(``TelegramChannel``, ``EmailChannel``, ...) for delivery.

Channels are intentionally universal: they accept a caller-composed
:class:`NotificationMessage` and deliver it. They do not localize, format
currency, or know anything about business alert semantics. Business / market
alert logic (price drop, out of stock, etc.) is a future consumer of this
submodule.
"""

from app.modules.alerts.notifications.base import (
    NotificationChannel,
    NotificationMessage,
)
from app.modules.alerts.notifications.email import EmailChannel
from app.modules.alerts.notifications.telegram import TelegramChannel

__all__ = [
    "NotificationChannel",
    "NotificationMessage",
    "TelegramChannel",
    "EmailChannel",
]
