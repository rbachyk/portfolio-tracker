from collections.abc import Generator
from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.dependencies import require_current_user
from app.config import Settings, get_settings
from app.db.models import Asset, Base, Symbol, SyncState
from app.db.session import get_db
from app.main import app
from app.services import sync_service
from app.services.sync_service import run_records_sync, run_sync_job


def make_session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def add_enabled_symbol(db: Session, symbol: str = "BTCUSDT") -> None:
    db.add_all(
        [
            Asset(code="BTC"),
            Asset(code="USDT"),
            Symbol(
                symbol=symbol,
                base_asset_code="BTC",
                quote_asset_code="USDT",
                status="TRADING",
                is_spot_trading_allowed=True,
                is_enabled=True,
            ),
        ]
    )
    db.commit()


def test_sync_spot_trades_skips_initial_sync_without_start_time() -> None:
    db = make_session()
    add_enabled_symbol(db)
    settings = Settings(binance_symbols="BTCUSDT", binance_trade_sync_start_ms=None)
    settings.binance_trade_sync_start_ms = None

    result = run_sync_job(db, settings, job_name="sync_spot_trades")

    assert result == {
        "job_name": "sync_spot_trades",
        "skipped": True,
        "reason": "BINANCE_TRADE_SYNC_START_MS is required before initial trade sync",
    }
    sync_state = db.scalar(select(SyncState).where(SyncState.job_name == "sync_spot_trades"))
    assert sync_state is not None
    assert sync_state.status == "skipped"
    assert sync_state.error_message == result["reason"]


def test_records_sync_continues_when_trade_backfill_start_time_is_missing(monkeypatch) -> None:
    db = make_session()
    add_enabled_symbol(db)
    settings = Settings(binance_symbols="BTCUSDT", binance_trade_sync_start_ms=None)
    settings.binance_trade_sync_start_ms = None
    settings.binance_history_sync_start_ms = None

    def fake_with_client(settings, run, job_name):  # noqa: ARG001
        return {"job_name": job_name, "count": 1}

    monkeypatch.setattr(sync_service, "_with_client", fake_with_client)

    result = run_records_sync(db, settings)

    assert result["job_name"] == "records_sync"
    assert result["results"]["sync_account_info"] == {
        "job_name": "sync_account_info",
        "count": 1,
    }
    assert result["results"]["sync_spot_trades"]["skipped"] is True
    assert result["results"]["sync_deposits"] == {
        "job_name": "sync_deposits",
        "skipped": True,
        "reason": "BINANCE_HISTORY_SYNC_START_MS is not configured",
    }
    assert result["results"]["sync_earn_positions"] == {
        "job_name": "sync_earn_positions",
        "count": 1,
    }
    assert result["results"]["sync_tracked_asset_prices"] == {
        "job_name": "sync_tracked_asset_prices",
        "count": 1,
    }


def test_records_sync_returns_failed_subjob_instead_of_raising(monkeypatch) -> None:
    db = make_session()
    settings = Settings()

    def fake_run_sync_job(db, settings, *, job_name):  # noqa: ARG001
        if job_name == "sync_deposits":
            raise RuntimeError("Binance API request failed with status 400")
        return {"job_name": job_name, "count": 1}

    monkeypatch.setattr(sync_service, "run_sync_job", fake_run_sync_job)

    result = run_records_sync(db, settings)

    assert result["results"]["sync_deposits"] == {
        "job_name": "sync_deposits",
        "failed": True,
        "error": "Binance API request failed with status 400",
    }
    assert result["results"]["sync_withdrawals"] == {
        "job_name": "sync_withdrawals",
        "count": 1,
    }


def test_history_windows_are_bounded_under_thirty_days() -> None:
    start_time_ms = int(datetime(2021, 1, 1, tzinfo=UTC).timestamp() * 1000)

    windows = sync_service._history_windows(start_time_ms)

    assert len(windows) > 1
    assert all(end_ms > start_ms for start_ms, end_ms in windows)
    assert all(
        end_ms - start_ms <= int(sync_service.HISTORY_WINDOW.total_seconds() * 1000)
        for start_ms, end_ms in windows
    )
    assert sync_service.HISTORY_WINDOW.days == 29


def test_records_sync_api_returns_skip_result_instead_of_500(monkeypatch) -> None:
    db = make_session()
    add_enabled_symbol(db)
    settings = Settings(binance_symbols="BTCUSDT", binance_trade_sync_start_ms=None)
    settings.binance_trade_sync_start_ms = None
    settings.binance_history_sync_start_ms = None

    def fake_with_client(settings, run, job_name):  # noqa: ARG001
        return {"job_name": job_name, "count": 1}

    def override_get_db() -> Generator[Session, None, None]:
        yield db

    monkeypatch.setattr(sync_service, "_with_client", fake_with_client)
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[require_current_user] = lambda: None
    app.dependency_overrides[get_settings] = lambda: settings

    try:
        response = TestClient(app).post("/api/sync/run", json={"job_name": "records_sync"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["results"]["sync_spot_trades"]["skipped"] is True
