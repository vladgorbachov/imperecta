"""Telegram linking + status response schemas.

CORE-TG1 dropped the Russian ``message`` field from generate-link-code:
the frontend builds its own localized prompt from ``{code}``.
"""

from pydantic import BaseModel


class TelegramLinkCodeResponse(BaseModel):
    """POST /telegram/generate-link-code body."""

    code: str
    bot_url: str


class TelegramUnlinkResponse(BaseModel):
    """POST /telegram/unlink body."""

    unlinked: bool


class TelegramStatusResponse(BaseModel):
    """GET /telegram/status body."""

    linked: bool
    chat_id: int | None
