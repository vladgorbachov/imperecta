"""Application settings loaded from environment variables."""

from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application configuration for cloud deploy (Railway + Supabase + Upstash)."""

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/imperecta"
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expiration_minutes: int = 30
    jwt_refresh_expiration_days: int = 7

    claude_api_key: str | None = None
    claude_model: str = "claude-sonnet-4-20250514"
    resend_api_key: str | None = None
    email_from: str = "noreply@imperecta.com"
    telegram_bot_token: str | None = None
    app_url: str = "https://imperecta-production.up.railway.app"

    proxy_list: str = ""
    proxy_sticky_duration: int = 10  # minutes for sticky session
    proxy_country_routing: bool = True  # use geo-targeted proxies
    sentry_dsn: str = ""
    allowed_origins: str = "http://localhost:5173"
    app_env: str = "development"
    port: int = 8000

    debug: bool = False

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        """Ensure DATABASE_URL uses asyncpg driver."""
        if not v.startswith("postgresql+asyncpg://"):
            raise ValueError("DATABASE_URL must start with postgresql+asyncpg://")
        return v

    @property
    def proxy_url(self) -> str | None:
        """Primary proxy URL from PROXY_LIST."""
        if not self.proxy_list:
            return None
        return self.proxy_list.split(",")[0].strip()

    @property
    def proxy_urls(self) -> list[str]:
        """All proxy URLs from PROXY_LIST."""
        if not self.proxy_list:
            return []
        return [p.strip() for p in self.proxy_list.split(",") if p.strip()]

    @property
    def origins_list(self) -> list[str]:
        """Return allowed origins as list of strings."""
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"
