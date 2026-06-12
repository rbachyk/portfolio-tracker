from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.accounting.events import AccountingEvent
from app.accounting.ledger_builder import build_ledger_events, rebuild_lots, trade_to_ledger_events
from app.accounting.lots import rebuild_lots_from_events
from app.accounting.pnl import calculate_lot_pnl, calculate_symbol_pnl
from app.db.models import Asset, Base, LedgerEvent, Lot, RawBinanceEvent, Symbol, Trade

EIGHTEEN_PLACES = Decimal("0.000000000000000001")
START = datetime(2024, 1, 1, tzinfo=UTC)


def make_session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def buy(
    event_id: str,
    asset: str,
    quantity: str,
    cost: str,
    *,
    days: int = 0,
    symbol: str | None = None,
) -> AccountingEvent:
    return AccountingEvent(
        event_type="SPOT_BUY",
        external_id=event_id,
        source_table="trades",
        source_id=1,
        symbol=symbol or f"{asset}USDT",
        asset_code=asset,
        quote_asset_code="USDT",
        quantity=Decimal(quantity),
        quote_quantity=Decimal(cost),
        unit_price=Decimal(cost) / Decimal(quantity),
        event_time=START + timedelta(days=days),
    )


def sell(
    event_id: str,
    asset: str,
    quantity: str,
    proceeds: str,
    *,
    days: int = 1,
) -> AccountingEvent:
    return AccountingEvent(
        event_type="SPOT_SELL",
        external_id=event_id,
        source_table="trades",
        source_id=2,
        symbol=f"{asset}USDT",
        asset_code=asset,
        quote_asset_code="USDT",
        quantity=-Decimal(quantity),
        quote_quantity=Decimal(proceeds),
        unit_price=Decimal(proceeds) / Decimal(quantity),
        event_time=START + timedelta(days=days),
    )


def reward(event_id: str, asset: str, quantity: str, *, days: int = 1) -> AccountingEvent:
    return AccountingEvent(
        event_type="EARN_REWARD",
        external_id=event_id,
        source_table="earn_rewards",
        source_id=3,
        asset_code=asset,
        quantity=Decimal(quantity),
        quote_quantity=Decimal("0"),
        event_time=START + timedelta(days=days),
    )


def transfer(
    event_type: str,
    event_id: str,
    asset: str,
    quantity: str,
    *,
    days: int,
) -> AccountingEvent:
    return AccountingEvent(
        event_type=event_type,
        external_id=event_id,
        source_table="earn_transfers",
        source_id=4,
        asset_code=asset,
        quantity=Decimal(quantity),
        quote_quantity=Decimal("0"),
        event_time=START + timedelta(days=days),
    )


def test_one_buy_no_rewards_has_lot_and_unrealized_pnl() -> None:
    result = rebuild_lots_from_events([buy("buy-1", "BTC", "1", "100")])

    assert len(result.lots) == 1
    lot_pnl = calculate_lot_pnl(result.lots[0], Decimal("150"))
    assert lot_pnl.remaining_quantity == Decimal("1")
    assert lot_pnl.cost_basis == Decimal("100")
    assert lot_pnl.market_value == Decimal("150")
    assert lot_pnl.unrealized_pnl == Decimal("50")


def test_multiple_buys_average_price_by_symbol() -> None:
    result = rebuild_lots_from_events(
        [
            buy("buy-1", "BTC", "1", "100"),
            buy("buy-2", "BTC", "1", "200", days=1),
        ]
    )

    pnl = calculate_symbol_pnl(result.lots, current_prices={"BTC": Decimal("250")})["BTC"]

    assert pnl.quantity == Decimal("2")
    assert pnl.average_buy_price == Decimal("150")
    assert pnl.cost_basis == Decimal("300")
    assert pnl.unrealized_pnl_including_rewards == Decimal("200")


def test_buy_with_fee_in_base_asset_reduces_lot_quantity() -> None:
    trade = Trade(
        id=1,
        symbol_id=1,
        raw_event_id=1,
        symbol="BTCUSDT",
        base_asset_code="BTC",
        quote_asset_code="USDT",
        side="BUY",
        binance_trade_id=10,
        binance_order_id=20,
        price=Decimal("100"),
        quantity=Decimal("1"),
        quote_quantity=Decimal("100"),
        fee_asset_code="BTC",
        fee_amount=Decimal("0.01"),
        executed_at=START,
        is_buyer=True,
        is_maker=False,
    )

    events = trade_to_ledger_events(trade)
    result = rebuild_lots_from_events(events)

    assert events[0].quantity == Decimal("0.99")
    assert events[0].quote_quantity == Decimal("100")
    assert result.lots[0].remaining_quantity == Decimal("0.99")
    assert result.lots[0].unit_cost.quantize(EIGHTEEN_PLACES) == Decimal(
        "101.010101010101010101"
    )


def test_buy_with_fee_in_bnb_keeps_asset_cost_basis_and_records_fee_event() -> None:
    trade = Trade(
        id=1,
        symbol_id=1,
        raw_event_id=1,
        symbol="BTCUSDT",
        base_asset_code="BTC",
        quote_asset_code="USDT",
        side="BUY",
        binance_trade_id=10,
        binance_order_id=20,
        price=Decimal("100"),
        quantity=Decimal("1"),
        quote_quantity=Decimal("100"),
        fee_asset_code="BNB",
        fee_amount=Decimal("0.1"),
        executed_at=START,
        is_buyer=True,
        is_maker=False,
    )

    events = trade_to_ledger_events(trade)
    result = rebuild_lots_from_events(events)

    assert [event.event_type for event in events] == ["SPOT_BUY", "TRADE_FEE"]
    assert result.lots[0].remaining_quantity == Decimal("1")
    assert result.lots[0].total_cost_basis == Decimal("100")
    assert events[1].asset_code == "BNB"
    assert events[1].quantity == Decimal("-0.1")


def test_earn_reward_after_buy_is_zero_cost_lot() -> None:
    result = rebuild_lots_from_events(
        [
            buy("buy-1", "BTC", "1", "100"),
            reward("reward-1", "BTC", "0.1"),
        ]
    )

    pnl = calculate_symbol_pnl(result.lots, current_prices={"BTC": Decimal("200")})["BTC"]

    assert pnl.quantity == Decimal("1.1")
    assert pnl.reward_quantity == Decimal("0.1")
    assert pnl.reward_value == Decimal("20.0")
    assert pnl.unrealized_pnl_including_rewards == Decimal("120.0")


def test_earn_subscription_and_redemption_do_not_create_lots_or_pnl() -> None:
    result = rebuild_lots_from_events(
        [
            buy("buy-1", "BTC", "1", "100"),
            transfer("EARN_SUBSCRIPTION", "sub-1", "BTC", "-1", days=1),
            transfer("EARN_REDEMPTION", "red-1", "BTC", "1", days=2),
        ]
    )

    pnl = calculate_symbol_pnl(result.lots, current_prices={"BTC": Decimal("150")})["BTC"]

    assert len(result.lots) == 1
    assert result.lots[0].remaining_quantity == Decimal("1")
    assert pnl.unrealized_pnl_including_rewards == Decimal("50")


def test_partial_sell_realizes_fifo_pnl_and_reduces_remaining_lot() -> None:
    result = rebuild_lots_from_events(
        [
            buy("buy-1", "BTC", "1", "100"),
            sell("sell-1", "BTC", "0.4", "80"),
        ]
    )

    pnl = calculate_symbol_pnl(result.lots, current_prices={"BTC": Decimal("250")})["BTC"]

    assert result.lots[0].remaining_quantity == Decimal("0.6")
    assert result.realized_pnl == Decimal("40.0")
    assert pnl.cost_basis == Decimal("60.0")
    assert pnl.unrealized_pnl_including_rewards == Decimal("90.0")


def test_multiple_assets_are_summarized_independently() -> None:
    result = rebuild_lots_from_events(
        [
            buy("btc-buy", "BTC", "1", "100"),
            buy("eth-buy", "ETH", "2", "50"),
        ]
    )

    pnl = calculate_symbol_pnl(
        result.lots,
        current_prices={"BTC": Decimal("120"), "ETH": Decimal("40")},
    )

    assert pnl["BTC"].market_value == Decimal("120")
    assert pnl["BTC"].unrealized_pnl_including_rewards == Decimal("20")
    assert pnl["ETH"].market_value == Decimal("80")
    assert pnl["ETH"].unrealized_pnl_including_rewards == Decimal("30")


def test_reward_included_vs_excluded_pnl_modes() -> None:
    result = rebuild_lots_from_events(
        [
            buy("buy-1", "BTC", "1", "100"),
            reward("reward-1", "BTC", "0.1"),
        ]
    )

    pnl = calculate_symbol_pnl(result.lots, current_prices={"BTC": Decimal("200")})["BTC"]

    assert pnl.unrealized_pnl_including_rewards == Decimal("120.0")
    assert pnl.unrealized_pnl_excluding_rewards == Decimal("100")
    assert pnl.reward_value == Decimal("20.0")


def test_ledger_build_and_lot_rebuild_are_idempotent() -> None:
    db = make_session()
    db.add_all([Asset(code="BTC"), Asset(code="USDT")])
    db.flush()
    symbol = Symbol(
        symbol="BTCUSDT",
        base_asset_code="BTC",
        quote_asset_code="USDT",
        status="TRADING",
        is_spot_trading_allowed=True,
        is_enabled=True,
    )
    raw_event = RawBinanceEvent(
        source="binance_spot",
        event_type="SPOT_TRADE",
        external_id="spot_trade:BTCUSDT:1",
        symbol="BTCUSDT",
        payload={"id": 1},
    )
    db.add_all([symbol, raw_event])
    db.flush()
    db.add(
        Trade(
            symbol_id=symbol.id,
            raw_event_id=raw_event.id,
            symbol="BTCUSDT",
            base_asset_code="BTC",
            quote_asset_code="USDT",
            side="BUY",
            binance_trade_id=1,
            binance_order_id=1,
            price=Decimal("100"),
            quantity=Decimal("1"),
            quote_quantity=Decimal("100"),
            fee_asset_code=None,
            fee_amount=Decimal("0"),
            executed_at=START,
            is_buyer=True,
            is_maker=False,
        )
    )
    db.commit()

    first_count = build_ledger_events(db)
    second_count = build_ledger_events(db)
    lot_count = rebuild_lots(db)

    assert first_count == 1
    assert second_count == 0
    assert len(db.scalars(select(LedgerEvent)).all()) == 1
    assert lot_count == 1
    lot = db.scalar(select(Lot))
    assert lot is not None
    assert lot.remaining_quantity == Decimal("1.000000000000000000")
