"""Application settings loaded from environment variables."""

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application configuration for cloud deploy (Railway + Supabase + Upstash)."""

    database_url: str
    redis_url: str
    jwt_secret: str
    jwt_algorithm: str
    jwt_expiration_minutes: int
    jwt_refresh_expiration_days: int
    jwt_refresh_expiration_days_remember: int

    claude_api_key: str | None = None
    market_data_forex_url: str
    market_data_crypto_url: str
    market_data_commodities_url: str | None = None
    goldapi_key: str | None = None
    alpha_vantage_key: str | None = None
    market_data_fuel_url: str | None = None
    market_data_timeout_seconds: int
    market_data_retry_attempts: int
    claude_model: str
    resend_api_key: str | None = None
    email_from: str
    telegram_bot_token: str | None = None
    telegram_bot_url: str | None = None
    telegram_webhook_secret: str | None = None  # Validates X-Telegram-Bot-Api-Secret-Token
    app_url: str

    proxy_list: str | None = None
    proxy_sticky_duration: int
    proxy_country_routing: bool

    decodo_api_url: str
    decodo_username: str | None = None
    decodo_password: str | None = None
    decodo_enabled: bool
    sentry_dsn: str | None = None
    allowed_origins: str
    app_env: str
    port: int

    debug: bool = False
    discovery_max_pages_per_run: int = 5000
    discovery_no_quota_limit: int = 200000
    scrape_pool_batch_size: int = 1000
    scrape_pool_max_listings_per_run: int = 200000
    # Pipeline orchestrator selector (O3). "tick" routes /run-pipeline through
    # the distributed orchestrator_tick state machine; anything else (default
    # "monolith") preserves the legacy run_full_pipeline_test path — fail-safe
    # to the proven implementation when the env var is unset or malformed.
    orchestrator_mode: str = "monolith"
    bootstrap_admin_email: str | None = None
    bootstrap_admin_password: str | None = None
    bootstrap_admin_name: str | None = None
    bootstrap_admin_language: str | None = None
    bootstrap_admin_plan: str | None = None

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        """Validate DATABASE_URL and normalize common SQLAlchemy-compatible forms."""
        value = v.strip()
        if not value:
            raise ValueError("DATABASE_URL is required and cannot be empty")

        # Supabase often provides a standard PostgreSQL URL. Normalize it for async SQLAlchemy.
        if value.startswith("postgresql://"):
            value = value.replace("postgresql://", "postgresql+asyncpg://", 1)

        if not value.startswith("postgresql+asyncpg://"):
            raise ValueError(
                "DATABASE_URL must start with postgresql+asyncpg:// "
                "or postgresql:// (auto-converted)"
            )
        return value

    @model_validator(mode="after")
    def validate_telegram_webhook_secret(self) -> "Settings":
        """When Telegram bot is enabled, webhook secret is required (all environments)."""
        if self.telegram_bot_token and not self.telegram_webhook_secret:
            raise ValueError(
                "TELEGRAM_WEBHOOK_SECRET must be set when TELEGRAM_BOT_TOKEN is configured. "
                "Configure both in environment for webhook security."
            )
        return self

    @model_validator(mode="after")
    def validate_bootstrap_admin(self) -> "Settings":
        """Bootstrap admin credentials must be provided as a pair."""
        if bool(self.bootstrap_admin_email) != bool(self.bootstrap_admin_password):
            raise ValueError(
                "BOOTSTRAP_ADMIN_EMAIL and BOOTSTRAP_ADMIN_PASSWORD must be set together."
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
        """Return allowed origins as list of strings."""
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"
