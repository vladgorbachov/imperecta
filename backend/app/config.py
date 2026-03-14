"""Application settings loaded from environment variables."""

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application configuration for cloud deploy (Railway + Supabase + Upstash)."""

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/imperecta"
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expiration_minutes: int = 30
    jwt_refresh_expiration_days: int = 7
    jwt_refresh_expiration_days_remember: int = 30  # "Remember me" refresh token TTL

    claude_api_key: str | None = None
    market_data_forex_url: str = "https://api.frankfurter.app/latest"
    market_data_crypto_url: str = "https://api.coingecko.com/api/v3/coins/markets"
    market_data_commodities_url: str = ""
    goldapi_key: str = ""  # GoldAPI.io: XAU, XAG, XPT, XPD (36h cache)
    alpha_vantage_key: str = ""  # Alpha Vantage: WTI, Brent, Natural Gas (24h cache)
    market_data_fuel_url: str = ""
    market_data_timeout_seconds: int = 15
    market_data_retry_attempts: int = 3
    claude_model: str = "claude-sonnet-4-20250514"
    resend_api_key: str | None = None
    email_from: str = "noreply@imperecta.com"
    telegram_bot_token: str | None = None
    telegram_webhook_secret: str | None = None  # Validates X-Telegram-Bot-Api-Secret-Token
    app_url: str = "https://imperecta-production.up.railway.app"

    proxy_list: str = ""
    proxy_sticky_duration: int = 10  # minutes for sticky session
    proxy_country_routing: bool = True  # use geo-targeted proxies
    sentry_dsn: str = ""
    allowed_origins: str = "http://localhost:5173,https://imperecta.pages.dev"
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

    @model_validator(mode="after")
    def validate_telegram_webhook_secret(self) -> "Settings":
        """When Telegram bot is enabled, webhook secret is required (all environments)."""
        if self.telegram_bot_token and not self.telegram_webhook_secret:
            raise ValueError(
                "TELEGRAM_WEBHOOK_SECRET must be set when TELEGRAM_BOT_TOKEN is configured. "
                "Configure both in environment for webhook security."
            )
        return self

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
        """Return allowed origins as list of strings. Always includes production frontend."""
        origins = [o.strip() for o in self.allowed_origins.split(",") if o.strip()]
        production_frontend = "https://imperecta.pages.dev"
        if production_frontend not in origins:
            origins.append(production_frontend)
        return origins

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"
