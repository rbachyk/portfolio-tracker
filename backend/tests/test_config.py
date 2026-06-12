from app.config import Settings


def test_blank_trade_sync_start_ms_is_treated_as_none() -> None:
    settings = Settings(_env_file=None, binance_trade_sync_start_ms="")

    assert settings.binance_trade_sync_start_ms is None
