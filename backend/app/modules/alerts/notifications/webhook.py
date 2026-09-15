"""Webhook channel strategy.

Delivers alert notifications as a JSON POST to a user-supplied HTTPS URL.
The channel carries zero business copy - the caller composes ``title`` /
``body`` and may attach a structured ``data`` payload for machine consumers.
"""

import logging

import httpx

from app.modules.alerts.notifications.base import NotificationChannel, NotificationMessage

logger = logging.getLogger(__name__)

_TIMEOUT_SECONDS = 10.0


class WebhookChannel(NotificationChannel):
    """POST the message as JSON to the recipient URL.

    The recipient is the rule's ``webhook_url`` (the alert door already
    enforced ``https://`` at rule-write time; this channel re-checks and
    fails soft on anything else).
    """

    async def send(self, recipient: str, message: NotificationMessage) -> bool:
        """Deliver ``message`` to an HTTPS webhook.

        Args:
            recipient: Destination URL. Must start with ``https://``.
            message: Caller-composed payload. Sent as
                ``{"title": ..., "message": ..., "data": {...}}``;
                ``parse_mode`` is ignored.

        Returns:
            ``True`` on any 2xx response; ``False`` on a non-HTTPS recipient,
            transport error, or non-2xx status.
        """
        if not (isinstance(recipient, str) and recipient.startswith("https://")):
            logger.warning("Webhook recipient is not an https URL: %r", recipient)
            return False

        payload: dict[str, object] = {
            "title": message.title,
            "message": message.body,
            "data": message.data or {},
        }
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
                response = await client.post(recipient, json=payload)
        except httpx.HTTPError as exc:
            logger.warning("Webhook delivery failed for %s: %s", recipient, exc)
            return False

        if not 200 <= response.status_code < 300:
            logger.warning(
                "Webhook non-2xx for %s: status=%s",
                recipient,
                response.status_code,
            )
            return False
        return True
