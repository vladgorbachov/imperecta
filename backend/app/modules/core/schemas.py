"""Residual core schemas (telegram link only).

CORE-AUTH1 moved the auth-only schemas to ``app.modules.auth.schemas``;
CORE-USERS1 moved UserResponse + UserUpdate to ``app.modules.users.schemas``.
The remaining TelegramLinkResponse stays here until the telegram extraction
pass takes ownership of /auth/telegram-link.
"""

from pydantic import BaseModel


class TelegramLinkResponse(BaseModel):
    code: str
    bot_url: str
