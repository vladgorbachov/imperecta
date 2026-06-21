"""Application settings loaded from environment variables."""

from pydantic import Field, field_validator, model_validator
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

  # Provider-neutral proxy fetch configuration (Stage 2).
    proxy_provider: str = "decodo"
    proxy_provider_rps: int = 10
    proxy_provider_api_url: str | None = Field(
        default=None,
        validation_alias="PROXY_PROVIDER_API_URL",
    )
    proxy_provider_username: str | None = Field(
        default=None,
        validation_alias="PROXY_PROVIDER_USERNAME",
    )
    proxy_provider_password: str | None = Field(
        default=None,
        validation_alias="PROXY_PROVIDER_PASSWORD",
    )
    proxy_provider_enabled: bool | None = Field(
        default=None,
        validation_alias="PROXY_PROVIDER_ENABLED",
    )

    # Deprecated DECODO_* env aliases — honored when neutral keys are unset.
    decodo_api_url: str | None = Field(default=None, validation_alias="DECODO_API_URL")
    decodo_username: str | None = Field(default=None, validation_alias="DECODO_USERNAME")
    decodo_password: str | None = Field(default=None, validation_alias="DECODO_PASSWORD")
    decodo_enabled: bool | None = Field(default=None, validation_alias="DECODO_ENABLED")
    sentry_dsn: str | None = None
    data_firewall_signing_secret: str | None = Field(
        default=None,
        validation_alias="DATA_FIREWALL_SIGNING_SECRET",
    )
    data_firewall_reject_spike_threshold: int = Field(
        default=50,
        validation_alias="DATA_FIREWALL_REJECT_SPIKE_THRESHOLD",
    )
    mv_refresh_temp_file_limit_mb: int = Field(
        default=256,
        validation_alias="MV_REFRESH_TEMP_FILE_LIMIT_MB",
    )
    mv_refresh_work_mem_mb: int = Field(
        default=64,
        validation_alias="MV_REFRESH_WORK_MEM_MB",
    )
    forex_allowed_currencies: str = Field(
        default="USD,EUR,GBP,JPY,CHF,MDL,RON,PLN,TRY",
        validation_alias="FOREX_ALLOWED_CURRENCIES",
    )
    allowed_origins: str
    app_env: str
    port: int

    debug: bool = False
    discovery_max_pages_per_run: int = 5000
    discovery_no_quota_limit: int = 200000
    scrape_pool_batch_size: int = 1000
    scrape_pool_max_listings_per_run: int = 200000
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
    def resolve_proxy_provider_config(self) -> "Settings":
        """Merge neutral proxy_provider_* with deprecated DECODO_* (neutral wins)."""
        api_url = self.proxy_provider_api_url or self.decodo_api_url
        if not api_url:
            raise ValueError(
                "PROXY_PROVIDER_API_URL or DECODO_API_URL (deprecated) is required"
            )
        username = (
            self.proxy_provider_username
            if self.proxy_provider_username is not None
            else self.decodo_username
        )
        password = (
            self.proxy_provider_password
            if self.proxy_provider_password is not None
            else self.decodo_password
        )
        if self.proxy_provider_enabled is not None:
            enabled = self.proxy_provider_enabled
        elif self.decodo_enabled is not None:
            enabled = self.decodo_enabled
        else:
            raise ValueError(
                "PROXY_PROVIDER_ENABLED or DECODO_ENABLED (deprecated) is required"
            )

        object.__setattr__(self, "proxy_provider_api_url", api_url)
        object.__setattr__(self, "proxy_provider_username", username)
        object.__setattr__(self, "proxy_provider_password", password)
        object.__setattr__(self, "proxy_provider_enabled", enabled)
        return self

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

    @property
    def forex_allowed_currency_set(self) -> frozenset[str]:
        """Fixed forex ingest/read allowlist (which currencies, not their rates)."""
        return frozenset(
            part.strip().upper()
            for part in self.forex_allowed_currencies.split(",")
            if part.strip()
        )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"
