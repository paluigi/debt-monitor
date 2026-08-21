"""Application settings, loaded from environment / .env."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration. Secrets come from the environment or .env."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    mongo_uri: str = "mongodb://localhost:27017"
    mongo_db_name: str = "debt_monitor"

    fred_api_key: str = ""
    fmp_api_key: str = ""
    finnhub_api_key: str = ""
    webshare_proxy: str = ""

    schedule_hour: int = 6
    schedule_minute: int = 0
    schedule_tz: str = "Europe/Rome"


@lru_cache
def get_settings() -> Settings:
    """Cached settings accessor (call settings_clear() in tests if needed)."""
    return Settings()
