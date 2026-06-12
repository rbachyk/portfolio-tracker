from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Binance Spot Portfolio Tracker"
    environment: str = "development"
    log_level: str = "INFO"
    api_prefix: str = "/api"
    database_url: str = "postgresql+psycopg://portfolio:portfolio@localhost:5432/portfolio"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
