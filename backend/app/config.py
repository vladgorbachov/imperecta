"""Application settings loaded from environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application configuration."""

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/priceradar"
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expiration_minutes: int = 30
    jwt_refresh_expiration_days: int = 7

    claude_api_key: str | None = None
    sendgrid_api_key: str | None = None
    telegram_bot_token: str | None = None

    proxy_list: str = ""

    debug: bool = False

    @property
    def proxy_list_parsed(self) -> list[str]:
        """Return proxy list as list of strings."""
        if not self.proxy_list:
            return []
        return [p.strip() for p in self.proxy_list.split(",") if p.strip()]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"
