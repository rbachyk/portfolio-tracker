from decimal import Decimal

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import Asset, Base, RawBinanceEvent, Symbol, SyncState, Trade
from app.ingestion.sync_trades import sync_spot_trades

EIGHT_PLACES = Decimal("0.00000001")


class FakeTradeClient:
    def __init__(self, trades_by_symbol: dict[str, list[dict]]) -> None:
        self.trades_by_symbol = trades_by_symbol
        self.calls: list[dict] = []

    def get_my_trades(
        self,
        *,
        symbol: str,
        from_id: int | None = None,
        start_time_ms: int | None = None,
        limit: int = 1000,
        **kwargs: object,
    ) -> list[dict]:
        self.calls.append(
            {
                "symbol": symbol,
                "from_id": from_id,
                "start_time_ms": start_time_ms,
                "limit": limit,
            }
        )
        trades = self.trades_by_symbol.get(symbol, [])
        if from_id is not None:
            trades = [trade for trade in trades if int(trade["id"]) >= from_id]
        return trades[:limit]


def make_session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def add_symbol(db: Session, symbol: str = "BTCUSDT") -> Symbol:
    db.add_all([Asset(code="BTC"), Asset(code="USDT")])
    db.flush()
    symbol_model = Symbol(
        symbol=symbol,
        base_asset_code="BTC",
        quote_asset_code="USDT",
        status="TRADING",
        is_spot_trading_allowed=True,
        is_enabled=True,
    )
    db.add(symbol_model)
    db.commit()
    return symbol_model


def trade_payload(
    trade_id: int,
    *,
    is_buyer: bool = True,
    commission_asset: str = "BNB",
) -> dict:
    return {
        "symbol": "BTCUSDT",
        "id": trade_id,
        "orderId": 1000 + trade_id,
        "orderListId": -1,
        "price": "50000.125",
        "qty": "0.01000000",
        "quoteQty": "500.00125000",
        "commission": "0.00075",
        "commissionAsset": commission_asset,
        "time": 1_700_000_000_000 + trade_id,
        "isBuyer": is_buyer,
        "isMaker": False,
        "isBestMatch": True,
    }


def test_spot_trade_sync_stores_raw_event_and_normalized_trade() -> None:
    db = make_session()
    add_symbol(db)
    client = FakeTradeClient({"BTCUSDT": [trade_payload(10)]})

    inserted = sync_spot_trades(db, client, start_time_ms=1_600_000_000_000)

    assert inserted == 1
    raw_event = db.scalar(select(RawBinanceEvent))
    assert raw_event is not None
    assert raw_event.source == "binance_spot"
    assert raw_event.event_type == "SPOT_TRADE"
    assert raw_event.external_id == "spot_trade:BTCUSDT:10"
    assert raw_event.payload["id"] == 10

    trade = db.scalar(select(Trade))
    assert trade is not None
    assert trade.raw_event_id == raw_event.id
    assert trade.symbol == "BTCUSDT"
    assert trade.side == "BUY"
    assert trade.binance_trade_id == 10
    assert trade.binance_order_id == 1010
    assert trade.base_asset_code == "BTC"
    assert trade.quote_asset_code == "USDT"
    assert trade.price == Decimal("50000.125000000000000000")
    assert trade.quantity == Decimal("0.010000000000000000")
    assert trade.quote_quantity.quantize(EIGHT_PLACES) == Decimal("500.00125000")
    assert trade.fee_asset_code == "BNB"
    assert trade.fee_amount == Decimal("0.000750000000000000")
    assert trade.is_buyer is True
    assert trade.is_maker is False

    sync_state = db.scalar(select(SyncState).where(SyncState.job_name == "sync_spot_trades"))
    assert sync_state is not None
    assert sync_state.status == "success"


def test_spot_trade_sync_is_idempotent_for_duplicate_payloads() -> None:
    db = make_session()
    add_symbol(db)
    client = FakeTradeClient({"BTCUSDT": [trade_payload(10)]})

    first_inserted = sync_spot_trades(db, client, start_time_ms=1_600_000_000_000)
    second_inserted = sync_spot_trades(db, client)

    assert first_inserted == 1
    assert second_inserted == 0
    assert len(db.scalars(select(RawBinanceEvent)).all()) == 1
    assert len(db.scalars(select(Trade)).all()) == 1
    assert client.calls[0]["start_time_ms"] == 1_600_000_000_000
    assert client.calls[1]["from_id"] == 11


def test_spot_trade_sync_requires_initial_start_time() -> None:
    db = make_session()
    add_symbol(db)
    client = FakeTradeClient({"BTCUSDT": [trade_payload(10)]})

    with pytest.raises(ValueError, match="requires BINANCE_TRADE_SYNC_START_MS"):
        sync_spot_trades(db, client)

    assert client.calls == []
    sync_state = db.scalar(select(SyncState).where(SyncState.job_name == "sync_spot_trades"))
    assert sync_state is not None
    assert sync_state.status == "failed"


def test_spot_trade_sync_uses_start_time_for_initial_backfill() -> None:
    db = make_session()
    add_symbol(db)
    client = FakeTradeClient({"BTCUSDT": []})

    sync_spot_trades(db, client, start_time_ms=1_600_000_000_000)

    assert client.calls == [
        {
            "symbol": "BTCUSDT",
            "from_id": None,
            "start_time_ms": 1_600_000_000_000,
            "limit": 1000,
        }
    ]


def test_spot_trade_sync_skips_symbols_not_in_configuration() -> None:
    db = make_session()
    client = FakeTradeClient({"ETHUSDT": [trade_payload(1)]})

    inserted = sync_spot_trades(db, client, symbols=["ETHUSDT"])

    assert inserted == 0
    assert client.calls == []


def test_spot_trade_sync_records_failed_sync_state() -> None:
    db = make_session()
    add_symbol(db)

    class FailingClient(FakeTradeClient):
        def get_my_trades(self, **kwargs: object) -> list[dict]:
            raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        sync_spot_trades(db, FailingClient({"BTCUSDT": []}), start_time_ms=1_600_000_000_000)

    sync_state = db.scalar(select(SyncState).where(SyncState.job_name == "sync_spot_trades"))
    assert sync_state is not None
    assert sync_state.status == "failed"
    assert sync_state.error_message == "boom"
