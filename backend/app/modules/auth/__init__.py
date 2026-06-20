"""Authentication module (Tier-1).

Public surface:
    - api.router: POST /auth/register, /auth/login, /auth/change-initial-password,
      /auth/refresh.
    - service: hash_password / verify_password / create_access_token /
      create_refresh_token / decode_token (bcrypt + JWT).
    - schemas: UserRegister, UserLogin, TokenResponse, RefreshTokenRequest,
      ChangeInitialPasswordRequest.

Self-profile (GET+PUT /users/me) lives in app.modules.users.api.self_router
(/api/users/me). Telegram link/disconnect routes live in app.modules.telegram.
"""
