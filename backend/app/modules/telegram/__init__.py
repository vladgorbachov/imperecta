"""Telegram module (Tier-1).

Public surface:
    - api.router: POST /telegram/webhook (secret-verified bot command handler),
      POST /telegram/generate-link-code, POST /telegram/unlink,
      GET /telegram/status.
    - schemas: TelegramLinkCodeResponse, TelegramStatusResponse,
      TelegramUnlinkResponse.

Bot replies are English module constants pending per-user-language
localization keyed off ``User.language`` (future i18n task; recorded — not
built in CORE-TG1). Telegram remains a consumer of
``app.modules.alerts.notifications`` via TelegramChannel (intentional).
"""
