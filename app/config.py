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

    # Database
    database_url: str = "sqlite:///./app.db"
    db_pool_size: int = 10

    # Security
    secret_key: str
    access_token_expire_minutes: int = 30

    # External APIs
    api_key: str | None = None


@lru_cache
def get_settings() -> Settings:
    """Cache settings to avoid re-reading .env on every request."""
    return Settings()
