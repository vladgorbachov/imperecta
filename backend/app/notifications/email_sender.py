"""Email notification sender via Resend."""

import asyncio
import logging
import re
from uuid import UUID

import resend

from app.config import Settings

logger = logging.getLogger(__name__)
settings = Settings()


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
    """Send alert email via Resend."""
    if not settings.resend_api_key:
        logger.warning("RESEND_API_KEY not set")
        return
    try:
        resend.api_key = settings.resend_api_key
        resend.Emails.send(
            {
                "from": settings.email_from,
                "to": [to],
                "subject": subject,
                "html": body_html,
            }
        )
    except Exception as e:
        logger.warning("Resend send failed: %s", e)


async def send_digest_email(to: str, digest_md: str) -> None:
    """Convert markdown to HTML and send digest email."""
    body_html = _md_to_html(digest_md)
    await send_alert_email(to, "Imperecta — Еженедельный дайджест", body_html)


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
                await send_alert_email(user.email, "Imperecta: Уведомление", body)

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
                await send_digest_email(user.email, content_md)

    asyncio.run(_do())
