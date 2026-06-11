"""Authentication module (Tier-1).

Public surface:
    - api.router: POST /auth/register, /auth/login, /auth/change-initial-password,
      /auth/refresh.
    - service: hash_password / verify_password / create_access_token /
      create_refresh_token / decode_token (bcrypt + JWT).
    - schemas: UserRegister, UserLogin, TokenResponse, RefreshTokenRequest,
      ChangeInitialPasswordRequest.

The /auth/me and /auth/telegram-link/disconnect routes still live in
app.modules.core.api_auth pending the users and telegram extraction passes.
"""
