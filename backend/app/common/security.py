"""Tier-0 security primitives: JWT decoding.

decode_token lives here (not in the auth module) so Tier-0 dependencies such
as app/common/deps.py can validate tokens without importing upward into
Tier-1 (app.modules.auth). Token *creation* and password hashing stay in
app.modules.auth.service, which re-exports decode_token for compatibility.
"""

from jose import jwt

from app.config import Settings

settings = Settings()


def decode_token(token: str) -> dict:
    """Decode and validate a JWT token. Raises jose.JWTError if invalid."""
    return jwt.decode(
        token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
    )
