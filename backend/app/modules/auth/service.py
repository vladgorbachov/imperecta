"""Authentication service: password hashing and JWT tokens."""

from datetime import datetime, timedelta, timezone
from uuid import UUID

from jose import jwt
from passlib.context import CryptContext

from app.common.security import decode_token  # noqa: F401  re-exported for callers
from app.config import Settings

settings = Settings()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash password using bcrypt."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify plain password against hashed password."""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(user_id: UUID, expires_delta: timedelta | None = None) -> str:
    """Create JWT access token for user."""
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.jwt_expiration_minutes)
    expire = datetime.now(timezone.utc) + expires_delta
    payload = {"sub": str(user_id), "exp": int(expire.timestamp()), "type": "access"}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_refresh_token(user_id: UUID, persistent: bool = False) -> tuple[str, datetime]:
    """Create JWT refresh token and return token + expiration."""
    days = settings.jwt_refresh_expiration_days_remember if persistent else settings.jwt_refresh_expiration_days
    expire = datetime.now(timezone.utc) + timedelta(days=days)
    payload = {
        "sub": str(user_id),
        "exp": int(expire.timestamp()),
        "type": "refresh",
        "persistent": persistent,
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, expire
