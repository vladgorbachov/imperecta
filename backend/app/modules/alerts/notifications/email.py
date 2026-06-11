"""Email channel strategy.

Delivers caller-composed messages via the Resend API. The channel contains
zero business copy - the caller provides a fully-rendered HTML body and an
optional title used as the email subject.
"""

import logging

import resend

from app.config import Settings
from app.modules.alerts.notifications.base import NotificationChannel, NotificationMessage

logger = logging.getLogger(__name__)
settings = Settings()


class EmailChannel(NotificationChannel):
    """Send transactional emails via Resend.

    Reads API key + sender from :class:`app.config.Settings`. If the API key
    is unset, :meth:`send` returns ``False`` instead of raising.
    """

    async def send(self, recipient: str, message: NotificationMessage) -> bool:
        """Deliver ``message`` to an email address.

        Args:
            recipient: Destination email address.
            message: Caller-composed payload. ``body`` is sent as the HTML
                body verbatim; ``title`` is used as the subject (required by
                the SMTP/Resend contract). ``parse_mode`` is ignored.

        Returns:
            ``True`` when Resend accepts the request; ``False`` when the API
            key is unset, the subject is missing, or Resend raises.
        """
        api_key = settings.resend_api_key
        if not api_key:
            return False
        if not message.title:
            logger.warning("Email send rejected: NotificationMessage.title (subject) is required")
            return False

        try:
            resend.api_key = api_key
            resend.Emails.send(
                {
                    "from": settings.email_from,
                    "to": [recipient],
                    "subject": message.title,
                    "html": message.body,
                }
            )
        except Exception as exc:
            logger.warning("Resend delivery failed for %s: %s", recipient, exc)
            return False
        return True
