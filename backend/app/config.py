from functools import lru_cache

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Binance Spot Portfolio Tracker"
    environment: str = "development"
    log_level: str = "INFO"
    api_prefix: str = "/api"
    database_url: str = (
        "postgresql+psycopg://crypto_portfolio_user:crypto_portfolio"
        "@localhost:5432/crypto_portfolio"
    )
    binance_base_url: str = "https://api.binance.com"
    binance_api_key: SecretStr | None = None
    binance_api_secret: SecretStr | None = None
    binance_recv_window_ms: int = 5000
    binance_symbols: str = ""
    binance_trade_sync_start_ms: int | None = None
    portfolio_base_asset: str = "USDT"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("binance_trade_sync_start_ms", mode="before")
    @classmethod
    def empty_optional_int_to_none(cls, value: object) -> object:
        if value == "":
            return None
        return value

    @property
    def configured_symbols(self) -> list[str]:
        return [
            symbol.strip().upper()
            for symbol in self.binance_symbols.split(",")
            if symbol.strip()
        ]

    @property
    def binance_api_key_value(self) -> str | None:
        if self.binance_api_key is None:
            return None
        value = self.binance_api_key.get_secret_value().strip()
        return value or None

    @property
    def binance_api_secret_value(self) -> str | None:
        if self.binance_api_secret is None:
            return None
        value = self.binance_api_secret.get_secret_value().strip()
        return value or None


@lru_cache
def get_settings() -> Settings:
    return Settings()
