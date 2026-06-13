from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import (
    Asset,
    Base,
    Deposit,
    LedgerEvent,
    Lot,
    PortfolioSnapshot,
    PriceSnapshot,
    RawBinanceEvent,
    Symbol,
    Withdrawal,
)
from app.db.session import get_db
from app.main import app
from app.services.portfolio_service import (
    MissingPriceError,
    create_portfolio_snapshot,
    get_drawdown_curve,
    get_equity_curve,
)

START = datetime(2024, 1, 1, tzinfo=UTC)
ZERO = Decimal("0")


def make_session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def add_asset(db: Session, code: str) -> None:
    if db.scalar(select(Asset).where(Asset.code == code)) is None:
        db.add(Asset(code=code))


def add_symbol_price(
    db: Session,
    *,
    symbol_name: str,
    base_asset: str,
    quote_asset: str,
    price: str,
    observed_at: datetime,
) -> None:
    add_asset(db, base_asset)
    add_asset(db, quote_asset)
    symbol = db.scalar(select(Symbol).where(Symbol.symbol == symbol_name))
    if symbol is None:
        symbol = Symbol(
            symbol=symbol_name,
            base_asset_code=base_asset,
            quote_asset_code=quote_asset,
            status="TRADING",
            is_spot_trading_allowed=True,
            is_enabled=True,
        )
        db.add(symbol)
        db.flush()

    db.add(
        PriceSnapshot(
            symbol_id=symbol.id,
            symbol=symbol_name,
            price=Decimal(price),
            observed_at=observed_at,
            raw_payload={"symbol": symbol_name, "price": price},
        )
    )


def add_lot(
    db: Session,
    *,
    asset: str,
    quantity: str,
    cost_basis: str,
    event_index: int,
    is_reward: bool = False,
    realized_pnl: str = "0",
) -> None:
    event_type = "EARN_REWARD" if is_reward else "SPOT_BUY"
    ledger_event = LedgerEvent(
        external_id=f"test:{event_index}",
        event_type=event_type,
        source_table="tests",
        source_id=event_index,
        symbol=f"{asset}USDT",
        asset_code=asset,
        quote_asset_code="USDT",
        quantity=Decimal(quantity),
        quote_quantity=Decimal(cost_basis),
        unit_price=ZERO
        if Decimal(quantity) == ZERO
        else Decimal(cost_basis) / Decimal(quantity),
        fee_amount=ZERO,
        event_time=START + timedelta(minutes=event_index),
        event_metadata={},
    )
    db.add(ledger_event)
    db.flush()
    db.add(
        Lot(
            source_ledger_event_id=ledger_event.id,
            asset_code=asset,
            symbol=f"{asset}USDT",
            source_type=event_type,
            opened_at=ledger_event.event_time,
            original_quantity=Decimal(quantity),
            remaining_quantity=Decimal(quantity),
            unit_cost=ledger_event.unit_price or ZERO,
            total_cost_basis=Decimal(cost_basis),
            realized_pnl=Decimal(realized_pnl),
            is_reward=is_reward,
        )
    )


def add_raw_event(db: Session, external_id: str) -> RawBinanceEvent:
    event = RawBinanceEvent(
        source="test",
        event_type="cash_flow",
        external_id=external_id,
        payload={"external_id": external_id},
    )
    db.add(event)
    db.flush()
    return event


def add_snapshot(
    db: Session,
    *,
    total_equity: str,
    net_deposited: str,
    days: int,
) -> None:
    db.add(
        PortfolioSnapshot(
            base_asset_code="USDT",
            total_equity=Decimal(total_equity),
            total_cost_basis=ZERO,
            total_deposited=Decimal(net_deposited),
            total_withdrawn=ZERO,
            net_deposited=Decimal(net_deposited),
            unrealized_pnl_including_rewards=ZERO,
            unrealized_pnl_excluding_rewards=ZERO,
            realized_pnl=ZERO,
            earn_rewards_value=ZERO,
            asset_count=0,
            holdings=[],
            missing_price_assets=[],
            snapshot_at=START + timedelta(days=days),
        )
    )


def test_create_portfolio_snapshot_uses_latest_price_and_reward_lots() -> None:
    db = make_session()
    add_symbol_price(
        db,
        symbol_name="BTCUSDT",
        base_asset="BTC",
        quote_asset="USDT",
        price="150",
        observed_at=START,
    )
    add_symbol_price(
        db,
        symbol_name="BTCUSDT",
        base_asset="BTC",
        quote_asset="USDT",
        price="200",
        observed_at=START + timedelta(minutes=1),
    )
    add_lot(db, asset="BTC", quantity="1", cost_basis="100", event_index=1)
    add_lot(
        db,
        asset="BTC",
        quantity="0.5",
        cost_basis="0",
        event_index=2,
        is_reward=True,
    )
    deposit_raw = add_raw_event(db, "deposit:1")
    withdrawal_raw = add_raw_event(db, "withdrawal:1")
    db.add(
        Deposit(
            raw_event_id=deposit_raw.id,
            external_id="deposit:1",
            asset_code="USDT",
            amount=Decimal("150"),
        )
    )
    db.add(
        Withdrawal(
            raw_event_id=withdrawal_raw.id,
            external_id="withdrawal:1",
            asset_code="USDT",
            amount=Decimal("20"),
            transaction_fee=Decimal("1"),
        )
    )
    db.commit()

    snapshot = create_portfolio_snapshot(
        db,
        base_asset="USDT",
        snapshot_at=START + timedelta(hours=1),
    )

    assert snapshot.total_equity == Decimal("300")
    assert snapshot.total_cost_basis == Decimal("100")
    assert snapshot.net_deposited == Decimal("129")
    assert snapshot.unrealized_pnl_including_rewards == Decimal("200")
    assert snapshot.unrealized_pnl_excluding_rewards == Decimal("100")
    assert snapshot.earn_rewards_value == Decimal("100")
    assert snapshot.asset_count == 1
    assert snapshot.holdings == [
        {
            "asset_code": "BTC",
            "quantity": "1.5",
            "average_buy_price": "100",
            "cost_basis": "100",
            "market_value": "300",
            "unrealized_pnl_including_rewards": "200",
            "unrealized_pnl_excluding_rewards": "100",
            "reward_quantity": "0.5",
            "reward_value": "100",
            "allocation_pct": "1",
        }
    ]


def test_create_portfolio_snapshot_fails_when_a_held_asset_has_no_price() -> None:
    db = make_session()
    add_lot(db, asset="ETH", quantity="2", cost_basis="50", event_index=1)
    db.commit()

    with pytest.raises(MissingPriceError) as exc_info:
        create_portfolio_snapshot(db, base_asset="USDT")

    assert exc_info.value.missing_assets == ["ETH"]


def test_equity_curve_and_drawdown_are_calculated_from_snapshots() -> None:
    db = make_session()
    add_snapshot(db, total_equity="100", net_deposited="90", days=0)
    add_snapshot(db, total_equity="120", net_deposited="90", days=1)
    add_snapshot(db, total_equity="90", net_deposited="90", days=2)
    add_snapshot(db, total_equity="150", net_deposited="100", days=3)
    db.commit()

    equity_curve = get_equity_curve(db)
    drawdown_curve = get_drawdown_curve(db)

    assert [point.total_equity for point in equity_curve] == [
        Decimal("100.000000000000000000"),
        Decimal("120.000000000000000000"),
        Decimal("90.000000000000000000"),
        Decimal("150.000000000000000000"),
    ]
    assert [point.equity_excluding_net_deposits for point in equity_curve] == [
        Decimal("10.000000000000000000"),
        Decimal("30.000000000000000000"),
        Decimal("0E-18"),
        Decimal("50.000000000000000000"),
    ]
    assert [point.drawdown for point in drawdown_curve] == [
        Decimal("0E-18"),
        Decimal("0E-18"),
        Decimal("-30.000000000000000000"),
        Decimal("0E-18"),
    ]
    assert drawdown_curve[2].drawdown_pct == Decimal("-0.250000000000000000")


def test_portfolio_snapshot_api_endpoints() -> None:
    db = make_session()
    add_symbol_price(
        db,
        symbol_name="BTCUSDT",
        base_asset="BTC",
        quote_asset="USDT",
        price="200",
        observed_at=START,
    )
    add_lot(db, asset="BTC", quantity="1", cost_basis="100", event_index=1)
    db.commit()

    def override_get_db() -> Generator[Session, None, None]:
        yield db

    app.dependency_overrides[get_db] = override_get_db

    try:
        client = TestClient(app)
        created_response = client.post("/api/portfolio/snapshots")
        latest_response = client.get("/api/portfolio/snapshots/latest")
        equity_response = client.get("/api/portfolio/performance/equity-curve")
        drawdown_response = client.get("/api/portfolio/performance/drawdown")
    finally:
        app.dependency_overrides.clear()

    assert created_response.status_code == 201
    assert created_response.json()["total_equity"] == "200"
    assert latest_response.status_code == 200
    assert latest_response.json()["total_equity"] == "200"
    assert equity_response.status_code == 200
    assert equity_response.json()["points"][0]["total_equity"] == "200"
    assert drawdown_response.status_code == 200
    assert drawdown_response.json()["points"][0]["drawdown"] == "0"
