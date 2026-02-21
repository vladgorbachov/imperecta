"""Email notification sender via SendGrid."""

import asyncio
import logging
import re
from uuid import UUID

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Content, Email, Mail

from app.config import Settings

logger = logging.getLogger(__name__)
settings = Settings()


def _send_sync(message: Mail) -> None:
    """Sync SendGrid send."""
    if not settings.sendgrid_api_key:
        return
    sg = SendGridAPIClient(settings.sendgrid_api_key)
    sg.send(message)


EMAIL_TEMPLATE = """
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><style>
body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px; }
.header { font-size: 24px; font-weight: bold; margin-bottom: 20px; color: #2563eb; }
.content { margin: 20px 0; }
.footer { font-size: 12px; color: #666; margin-top: 30px; border-top: 1px solid #eee; padding-top: 15px; }
</style></head>
<body>
<div class="header">PriceRadar</div>
<div class="content">{body}</div>
<div class="footer">PriceRadar — мониторинг цен конкурентов</div>
</body>
</html>
"""


def _md_to_html(md: str) -> str:
    """Simple markdown to HTML conversion."""
    html = md.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    html = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html)
    html = re.sub(r"\*(.+?)\*", r"<em>\1</em>", html)
    html = re.sub(r"^### (.+)$", r"<h3>\1</h3>", html, flags=re.MULTILINE)
    html = re.sub(r"^## (.+)$", r"<h2>\1</h2>", html, flags=re.MULTILINE)
    html = re.sub(r"^# (.+)$", r"<h1>\1</h1>", html, flags=re.MULTILINE)
    html = re.sub(r"\n\n", "</p><p>", html)
    html = re.sub(r"\n", "<br>", html)
    return f"<p>{html}</p>"


async def send_alert_email(to: str, subject: str, body_html: str) -> None:
    """Send alert email via SendGrid. Simple HTML template."""
    if not settings.sendgrid_api_key:
        logger.warning("SENDGRID_API_KEY not set")
        return

    body = EMAIL_TEMPLATE.format(body=body_html)
    message = Mail(
        from_email=Email("noreply@priceradar.app", "PriceRadar"),
        to_emails=to,
        subject=subject,
        html_content=Content("text/html", body),
    )
    try:
        await asyncio.to_thread(_send_sync, message)
    except Exception as e:
        logger.warning("SendGrid send failed: %s", e)


async def send_digest_email(to: str, digest_md: str, subject: str = "PriceRadar: Дайджест") -> None:
    """Convert markdown to HTML and send digest email."""
    body_html = _md_to_html(digest_md)
    await send_alert_email(to, subject, body_html)


def send_alert_email_to_user(user_id: UUID, message: str) -> None:
    """Sync wrapper for Celery: fetch user email, send alert."""
    import asyncio

    from sqlalchemy import select

    from app.database import async_session_maker
    from app.models import User

    async def _do():
        async with async_session_maker() as session:
            result = await session.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()
            if user:
                body = f"<p>{message.replace('<', '&lt;').replace('>', '&gt;')}</p>"
                await send_alert_email(user.email, "PriceRadar: Уведомление", body)

    asyncio.run(_do())


def send_digest_email_to_user(user_id: UUID, subject: str, content_md: str) -> None:
    """Sync wrapper for Celery: fetch user email, send digest."""
    import asyncio

    from sqlalchemy import select

    from app.database import async_session_maker
    from app.models import User

    async def _do():
        async with async_session_maker() as session:
            result = await session.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()
            if user:
                await send_digest_email(user.email, content_md, subject)

    asyncio.run(_do())
