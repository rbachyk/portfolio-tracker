from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def utc_now() -> datetime:
    return datetime.now(UTC)


class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    name: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class Symbol(Base):
    __tablename__ = "symbols"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    base_asset_code: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("assets.code"), index=True
    )
    quote_asset_code: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("assets.code"), index=True
    )
    status: Mapped[str | None] = mapped_column(String(32), index=True)
    is_spot_trading_allowed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    raw_payload: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    base_asset: Mapped[Asset | None] = relationship(
        "Asset", foreign_keys=[base_asset_code], primaryjoin=base_asset_code == Asset.code
    )
    quote_asset: Mapped[Asset | None] = relationship(
        "Asset", foreign_keys=[quote_asset_code], primaryjoin=quote_asset_code == Asset.code
    )


class PriceSnapshot(Base):
    __tablename__ = "price_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol_id: Mapped[int] = mapped_column(ForeignKey("symbols.id"), index=True, nullable=False)
    symbol: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    source: Mapped[str] = mapped_column(String(64), default="binance_ticker_price", nullable=False)
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, index=True
    )
    raw_payload: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    symbol_ref: Mapped[Symbol] = relationship("Symbol")


class SyncState(Base):
    __tablename__ = "sync_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    last_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)
    progress_current: Mapped[int | None] = mapped_column(Integer)
    progress_total: Mapped[int | None] = mapped_column(Integer)
    progress_message: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


Index("ix_price_snapshots_symbol_observed_at", PriceSnapshot.symbol, PriceSnapshot.observed_at)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class Setting(Base):
    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    value: Mapped[dict | list | str | int | float | bool | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class TargetAllocation(Base):
    __tablename__ = "target_allocations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    asset_code: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    target_pct: Mapped[Decimal] = mapped_column(Numeric(18, 10), nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class SpotBalance(Base):
    __tablename__ = "spot_balances"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    raw_event_id: Mapped[int | None] = mapped_column(ForeignKey("raw_binance_events.id"))
    asset_code: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    free: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    locked: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    total: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    snapshot_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, index=True, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    raw_event: Mapped["RawBinanceEvent | None"] = relationship("RawBinanceEvent")


class RawBinanceEvent(Base):
    __tablename__ = "raw_binance_events"
    __table_args__ = (
        UniqueConstraint("source", "external_id", name="uq_raw_binance_events_source_external_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    external_id: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    symbol: Mapped[str | None] = mapped_column(String(32), index=True)
    event_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class ManualAdjustment(Base):
    __tablename__ = "manual_adjustments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    external_id: Mapped[str] = mapped_column(String(256), unique=True, index=True, nullable=False)
    asset_code: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    symbol: Mapped[str | None] = mapped_column(String(32), index=True)
    quote_asset_code: Mapped[str | None] = mapped_column(String(32), index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    quote_quantity: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(38, 18))
    reason: Mapped[str | None] = mapped_column(Text)
    adjusted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, index=True, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class Trade(Base):
    __tablename__ = "trades"
    __table_args__ = (
        UniqueConstraint("symbol", "binance_trade_id", name="uq_trades_symbol_binance_trade_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol_id: Mapped[int] = mapped_column(ForeignKey("symbols.id"), index=True, nullable=False)
    raw_event_id: Mapped[int] = mapped_column(ForeignKey("raw_binance_events.id"), nullable=False)
    symbol: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    base_asset_code: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    quote_asset_code: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    side: Mapped[str] = mapped_column(String(8), index=True, nullable=False)
    binance_trade_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    binance_order_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    binance_order_list_id: Mapped[int | None] = mapped_column(BigInteger)
    price: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    quote_quantity: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    fee_asset_code: Mapped[str | None] = mapped_column(String(32), index=True)
    fee_amount: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    executed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True, nullable=False
    )
    is_buyer: Mapped[bool] = mapped_column(Boolean, nullable=False)
    is_maker: Mapped[bool] = mapped_column(Boolean, nullable=False)
    is_best_match: Mapped[bool | None] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    raw_event: Mapped[RawBinanceEvent] = relationship("RawBinanceEvent")
    symbol_ref: Mapped[Symbol] = relationship("Symbol")


class Deposit(Base):
    __tablename__ = "deposits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    raw_event_id: Mapped[int] = mapped_column(ForeignKey("raw_binance_events.id"), nullable=False)
    external_id: Mapped[str] = mapped_column(String(256), unique=True, index=True, nullable=False)
    asset_code: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    network: Mapped[str | None] = mapped_column(String(64), index=True)
    status: Mapped[int | None] = mapped_column(Integer, index=True)
    address: Mapped[str | None] = mapped_column(Text)
    address_tag: Mapped[str | None] = mapped_column(String(256))
    tx_id: Mapped[str | None] = mapped_column(String(512), index=True)
    transfer_type: Mapped[int | None] = mapped_column(Integer)
    wallet_type: Mapped[int | None] = mapped_column(Integer)
    inserted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    raw_event: Mapped[RawBinanceEvent] = relationship("RawBinanceEvent")


class Withdrawal(Base):
    __tablename__ = "withdrawals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    raw_event_id: Mapped[int] = mapped_column(ForeignKey("raw_binance_events.id"), nullable=False)
    external_id: Mapped[str] = mapped_column(String(256), unique=True, index=True, nullable=False)
    asset_code: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    transaction_fee: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    network: Mapped[str | None] = mapped_column(String(64), index=True)
    status: Mapped[int | None] = mapped_column(Integer, index=True)
    address: Mapped[str | None] = mapped_column(Text)
    tx_id: Mapped[str | None] = mapped_column(String(512), index=True)
    withdraw_order_id: Mapped[str | None] = mapped_column(String(256), index=True)
    transfer_type: Mapped[int | None] = mapped_column(Integer)
    wallet_type: Mapped[int | None] = mapped_column(Integer)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    raw_event: Mapped[RawBinanceEvent] = relationship("RawBinanceEvent")


class P2POrder(Base):
    __tablename__ = "p2p_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    raw_event_id: Mapped[int] = mapped_column(ForeignKey("raw_binance_events.id"), nullable=False)
    external_id: Mapped[str] = mapped_column(String(256), unique=True, index=True, nullable=False)
    order_number: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    trade_type: Mapped[str] = mapped_column(String(16), index=True, nullable=False)
    asset_code: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    fiat_code: Mapped[str | None] = mapped_column(String(16), index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    total_price: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(38, 18))
    commission: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    order_status: Mapped[str | None] = mapped_column(String(64), index=True)
    pay_method_name: Mapped[str | None] = mapped_column(String(128))
    order_created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    raw_event: Mapped[RawBinanceEvent] = relationship("RawBinanceEvent")


class FundingTransfer(Base):
    __tablename__ = "funding_transfers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    raw_event_id: Mapped[int] = mapped_column(ForeignKey("raw_binance_events.id"), nullable=False)
    external_id: Mapped[str] = mapped_column(String(256), unique=True, index=True, nullable=False)
    tran_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    transfer_type: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    asset_code: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    status: Mapped[str | None] = mapped_column(String(64), index=True)
    transferred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    raw_event: Mapped[RawBinanceEvent] = relationship("RawBinanceEvent")


class EarnPosition(Base):
    __tablename__ = "earn_positions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    raw_event_id: Mapped[int] = mapped_column(ForeignKey("raw_binance_events.id"), nullable=False)
    external_id: Mapped[str] = mapped_column(String(256), unique=True, index=True, nullable=False)
    product_type: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    product_id: Mapped[str | None] = mapped_column(String(128), index=True)
    asset_code: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    auto_subscribe: Mapped[bool | None] = mapped_column(Boolean)
    snapshot_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    raw_event: Mapped[RawBinanceEvent] = relationship("RawBinanceEvent")


class EarnSubscription(Base):
    __tablename__ = "earn_subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    raw_event_id: Mapped[int] = mapped_column(ForeignKey("raw_binance_events.id"), nullable=False)
    external_id: Mapped[str] = mapped_column(String(256), unique=True, index=True, nullable=False)
    product_type: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    purchase_id: Mapped[str | None] = mapped_column(String(128), index=True)
    product_id: Mapped[str | None] = mapped_column(String(128), index=True)
    asset_code: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    source_endpoint: Mapped[str] = mapped_column(String(128), nullable=False)
    subscribed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    raw_event: Mapped[RawBinanceEvent] = relationship("RawBinanceEvent")


class EarnRedemption(Base):
    __tablename__ = "earn_redemptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    raw_event_id: Mapped[int] = mapped_column(ForeignKey("raw_binance_events.id"), nullable=False)
    external_id: Mapped[str] = mapped_column(String(256), unique=True, index=True, nullable=False)
    product_type: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    redeem_id: Mapped[str | None] = mapped_column(String(128), index=True)
    product_id: Mapped[str | None] = mapped_column(String(128), index=True)
    asset_code: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    source_endpoint: Mapped[str] = mapped_column(String(128), nullable=False)
    redeemed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    raw_event: Mapped[RawBinanceEvent] = relationship("RawBinanceEvent")


class EarnReward(Base):
    __tablename__ = "earn_rewards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    raw_event_id: Mapped[int] = mapped_column(ForeignKey("raw_binance_events.id"), nullable=False)
    external_id: Mapped[str] = mapped_column(String(256), unique=True, index=True, nullable=False)
    product_type: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    product_id: Mapped[str | None] = mapped_column(String(128), index=True)
    asset_code: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    reward_type: Mapped[str | None] = mapped_column(String(64), index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    cost_basis_mode: Mapped[str] = mapped_column(String(32), default="ZERO", nullable=False)
    source_endpoint: Mapped[str] = mapped_column(String(128), nullable=False)
    rewarded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    raw_event: Mapped[RawBinanceEvent] = relationship("RawBinanceEvent")


class LedgerEvent(Base):
    __tablename__ = "ledger_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    external_id: Mapped[str] = mapped_column(String(256), unique=True, index=True, nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    source_table: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    source_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    symbol: Mapped[str | None] = mapped_column(String(32), index=True)
    asset_code: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    quote_asset_code: Mapped[str | None] = mapped_column(String(32), index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    quote_quantity: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(38, 18))
    fee_asset_code: Mapped[str | None] = mapped_column(String(32), index=True)
    fee_amount: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    event_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True, nullable=False
    )
    event_metadata: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class Lot(Base):
    __tablename__ = "lots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_ledger_event_id: Mapped[int] = mapped_column(
        ForeignKey("ledger_events.id"), index=True, nullable=False
    )
    asset_code: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    symbol: Mapped[str | None] = mapped_column(String(32), index=True)
    source_type: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    original_quantity: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    remaining_quantity: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    total_cost_basis: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    realized_pnl: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    is_reward: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    source_ledger_event: Mapped[LedgerEvent] = relationship("LedgerEvent")


class PortfolioSnapshot(Base):
    __tablename__ = "portfolio_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    base_asset_code: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    total_equity: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    total_cost_basis: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    total_deposited: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    total_withdrawn: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    net_deposited: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    unrealized_pnl_including_rewards: Mapped[Decimal] = mapped_column(
        Numeric(38, 18), nullable=False
    )
    unrealized_pnl_excluding_rewards: Mapped[Decimal] = mapped_column(
        Numeric(38, 18), nullable=False
    )
    realized_pnl: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    earn_rewards_value: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    asset_count: Mapped[int] = mapped_column(Integer, nullable=False)
    holdings: Mapped[list[dict]] = mapped_column(JSON, nullable=False)
    missing_price_assets: Mapped[list[str] | None] = mapped_column(JSON)
    snapshot_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, index=True, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
