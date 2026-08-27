from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # Ignore extra env vars not defined here
    )

    # App
    app_name: str = "EventHub"
    debug: bool = False

    database_url: str = "sqlite+aiosqlite:///./app.db"
    db_pool_size: int = 10

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Environment
    environment: str = "production"

    # CORS
    cors_origins: list[str] = ["*"]

    # Security
    secret_key: str
    access_token_expire_minutes: int = 30

    # RSA Keys (optional: load from env vars directly)
    rsa_private_key: str | None = None
    rsa_public_key: str | None = None

    # Or load from files
    rsa_private_key_path: str = "./scripts/private_key.pem"
    rsa_public_key_path: str = "./scripts/public_key.pem"

    # External APIs
    api_key: str | None = None

    # Rate limiting
    rate_limit_enabled: bool = True
    rate_limit_max_requests: int = 100
    rate_limit_window_seconds: int = 60

    reservation_window_minutes: int = 10


@lru_cache
def get_settings() -> Settings:
    """Cache settings to avoid re-reading .env on every request."""
    return Settings()
