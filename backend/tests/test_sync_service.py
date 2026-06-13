from collections.abc import Generator
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.dependencies import require_current_user
from app.config import Settings, get_settings
from app.db.models import Asset, Base, EarnReward, RawBinanceEvent, Symbol, SyncState
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
    settings = Settings(
        binance_symbols="BTCUSDT",
        binance_trade_sync_start_ms=None,
        binance_history_sync_start_ms=None,
    )
    settings.binance_trade_sync_start_ms = None
    settings.binance_history_sync_start_ms = None

    result = run_sync_job(db, settings, job_name="sync_spot_trades")

    assert result == {
        "job_name": "sync_spot_trades",
        "skipped": True,
        "reason": (
            "BINANCE_TRADE_SYNC_START_MS or BINANCE_HISTORY_SYNC_START_MS is required "
            "before initial trade sync"
        ),
    }
    sync_state = db.scalar(select(SyncState).where(SyncState.job_name == "sync_spot_trades"))
    assert sync_state is not None
    assert sync_state.status == "skipped"
    assert sync_state.error_message == result["reason"]


def test_sync_spot_trades_uses_history_start_time_for_initial_backfill(monkeypatch) -> None:
    db = make_session()
    add_enabled_symbol(db)
    settings = Settings(
        binance_symbols="BTCUSDT",
        binance_trade_sync_start_ms=None,
        binance_history_sync_start_ms=1_609_459_200_000,
    )
    captured: dict[str, int | None] = {}

    class FakeClient:
        def get_my_trades(self, **params):
            captured["start_time_ms"] = params["start_time_ms"]
            return []

    def fake_with_client(settings, run, job_name):  # noqa: ARG001
        return {"job_name": job_name, "count": run(FakeClient())}

    monkeypatch.setattr(sync_service, "_with_client", fake_with_client)

    result = run_sync_job(db, settings, job_name="sync_spot_trades")

    assert result == {"job_name": "sync_spot_trades", "count": 0}
    assert captured["start_time_ms"] == 1_609_459_200_000
    sync_state = db.scalar(select(SyncState).where(SyncState.job_name == "sync_spot_trades"))
    assert sync_state is not None
    assert sync_state.status == "success"
    assert sync_state.progress_current == 1
    assert sync_state.progress_total == 1


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
    assert result["results"]["sync_p2p_orders"] == {
        "job_name": "sync_p2p_orders",
        "skipped": True,
        "reason": "BINANCE_HISTORY_SYNC_START_MS is not configured",
    }
    p2p_state = db.scalar(select(SyncState).where(SyncState.job_name == "sync_p2p_orders"))
    assert p2p_state is not None
    assert p2p_state.progress_current == 0
    assert p2p_state.progress_total == 0
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


def test_incremental_earn_history_start_uses_latest_record_with_overlap() -> None:
    db = make_session()
    rewarded_at = datetime(2024, 1, 10, tzinfo=UTC)
    raw_event = RawBinanceEvent(
        source="binance_simple_earn",
        event_type="EARN_REWARD",
        external_id="reward:1",
        payload={"asset": "USDT", "rewards": "1"},
    )
    db.add(raw_event)
    db.flush()
    db.add(
        EarnReward(
            raw_event_id=raw_event.id,
            external_id="reward:1",
            product_type="flexible",
            asset_code="USDT",
            amount=1,
            cost_basis_mode="ZERO",
            source_endpoint="simple-earn/flexible/rewardsRecord",
            rewarded_at=rewarded_at,
        )
    )
    db.commit()
    settings = Settings(
        binance_history_sync_start_ms=int(datetime(2024, 1, 1, tzinfo=UTC).timestamp() * 1000)
    )

    start_ms = sync_service._incremental_history_start_ms(
        db,
        settings,
        EarnReward.rewarded_at,
    )

    assert start_ms == int((rewarded_at - timedelta(days=2)).timestamp() * 1000)


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
