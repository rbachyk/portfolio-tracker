from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.accounting.lots import LotState
from app.accounting.pnl import SymbolPnL, calculate_symbol_pnl
from app.db.models import (
    Deposit,
    Lot,
    PortfolioSnapshot,
    PriceSnapshot,
    Symbol,
    Withdrawal,
    utc_now,
)

ZERO = Decimal("0")
ONE = Decimal("1")


class MissingPriceError(ValueError):
    def __init__(self, missing_assets: list[str]) -> None:
        self.missing_assets = missing_assets
        super().__init__(f"Missing current prices for: {', '.join(missing_assets)}")


@dataclass(frozen=True)
class EquityCurvePoint:
    snapshot_at: datetime
    total_equity: Decimal
    net_deposited: Decimal
    equity_excluding_net_deposits: Decimal


@dataclass(frozen=True)
class DrawdownPoint:
    snapshot_at: datetime
    total_equity: Decimal
    peak_equity: Decimal
    drawdown: Decimal
    drawdown_pct: Decimal | None


def create_portfolio_snapshot(
    db: Session,
    *,
    base_asset: str,
    snapshot_at: datetime | None = None,
) -> PortfolioSnapshot:
    base_asset = base_asset.strip().upper()
    lots = _load_lots(db)
    current_prices = _latest_prices_by_asset(db, base_asset=base_asset)
    missing_assets = _missing_price_assets(lots, current_prices)
    if missing_assets:
        raise MissingPriceError(missing_assets)

    symbol_pnl = calculate_symbol_pnl(lots, current_prices=current_prices)
    total_equity = sum((item.market_value for item in symbol_pnl.values()), ZERO)
    total_cost_basis = sum((item.cost_basis for item in symbol_pnl.values()), ZERO)
    earn_rewards_value = sum((item.reward_value for item in symbol_pnl.values()), ZERO)
    realized_pnl = sum((lot.realized_pnl for lot in lots), ZERO)
    total_deposited, total_withdrawn = _base_asset_cash_flows(db, base_asset)

    snapshot = PortfolioSnapshot(
        base_asset_code=base_asset,
        total_equity=total_equity,
        total_cost_basis=total_cost_basis,
        total_deposited=total_deposited,
        total_withdrawn=total_withdrawn,
        net_deposited=total_deposited - total_withdrawn,
        unrealized_pnl_including_rewards=sum(
            (item.unrealized_pnl_including_rewards for item in symbol_pnl.values()),
            ZERO,
        ),
        unrealized_pnl_excluding_rewards=sum(
            (item.unrealized_pnl_excluding_rewards for item in symbol_pnl.values()),
            ZERO,
        ),
        realized_pnl=realized_pnl,
        earn_rewards_value=earn_rewards_value,
        asset_count=len(symbol_pnl),
        holdings=_holdings_payload(symbol_pnl, total_equity),
        missing_price_assets=[],
        snapshot_at=snapshot_at or utc_now(),
    )
    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)
    return snapshot


def get_latest_portfolio_snapshot(db: Session) -> PortfolioSnapshot | None:
    return db.scalar(
        select(PortfolioSnapshot)
        .order_by(desc(PortfolioSnapshot.snapshot_at), desc(PortfolioSnapshot.id))
        .limit(1)
    )


def list_portfolio_snapshots(db: Session, *, limit: int = 100) -> list[PortfolioSnapshot]:
    return list(
        db.scalars(
            select(PortfolioSnapshot)
            .order_by(desc(PortfolioSnapshot.snapshot_at), desc(PortfolioSnapshot.id))
            .limit(limit)
        )
    )


def get_equity_curve(db: Session, *, limit: int = 365) -> list[EquityCurvePoint]:
    return [
        EquityCurvePoint(
            snapshot_at=snapshot.snapshot_at,
            total_equity=snapshot.total_equity,
            net_deposited=snapshot.net_deposited,
            equity_excluding_net_deposits=snapshot.total_equity - snapshot.net_deposited,
        )
        for snapshot in _snapshot_window_chronological(db, limit=limit)
    ]


def get_drawdown_curve(db: Session, *, limit: int = 365) -> list[DrawdownPoint]:
    points: list[DrawdownPoint] = []
    peak_equity = ZERO
    for snapshot in _snapshot_window_chronological(db, limit=limit):
        if snapshot.total_equity > peak_equity:
            peak_equity = snapshot.total_equity
        drawdown = snapshot.total_equity - peak_equity
        points.append(
            DrawdownPoint(
                snapshot_at=snapshot.snapshot_at,
                total_equity=snapshot.total_equity,
                peak_equity=peak_equity,
                drawdown=drawdown,
                drawdown_pct=None if peak_equity == ZERO else drawdown / peak_equity,
            )
        )
    return points


def portfolio_snapshot_to_dict(snapshot: PortfolioSnapshot) -> dict:
    return {
        "id": snapshot.id,
        "base_asset": snapshot.base_asset_code,
        "snapshot_at": snapshot.snapshot_at.isoformat(),
        "total_equity": decimal_to_string(snapshot.total_equity),
        "total_cost_basis": decimal_to_string(snapshot.total_cost_basis),
        "total_deposited": decimal_to_string(snapshot.total_deposited),
        "total_withdrawn": decimal_to_string(snapshot.total_withdrawn),
        "net_deposited": decimal_to_string(snapshot.net_deposited),
        "unrealized_pnl_including_rewards": decimal_to_string(
            snapshot.unrealized_pnl_including_rewards
        ),
        "unrealized_pnl_excluding_rewards": decimal_to_string(
            snapshot.unrealized_pnl_excluding_rewards
        ),
        "realized_pnl": decimal_to_string(snapshot.realized_pnl),
        "earn_rewards_value": decimal_to_string(snapshot.earn_rewards_value),
        "asset_count": snapshot.asset_count,
        "holdings": snapshot.holdings,
        "missing_price_assets": snapshot.missing_price_assets or [],
    }


def equity_curve_point_to_dict(point: EquityCurvePoint) -> dict:
    return {
        "snapshot_at": point.snapshot_at.isoformat(),
        "total_equity": decimal_to_string(point.total_equity),
        "net_deposited": decimal_to_string(point.net_deposited),
        "equity_excluding_net_deposits": decimal_to_string(
            point.equity_excluding_net_deposits
        ),
    }


def drawdown_point_to_dict(point: DrawdownPoint) -> dict:
    return {
        "snapshot_at": point.snapshot_at.isoformat(),
        "total_equity": decimal_to_string(point.total_equity),
        "peak_equity": decimal_to_string(point.peak_equity),
        "drawdown": decimal_to_string(point.drawdown),
        "drawdown_pct": None
        if point.drawdown_pct is None
        else decimal_to_string(point.drawdown_pct),
    }


def decimal_to_string(value: Decimal) -> str:
    return format(value.normalize(), "f")


def _load_lots(db: Session) -> list[LotState]:
    return [
        LotState(
            source_event_id=str(lot.source_ledger_event_id),
            asset_code=lot.asset_code,
            symbol=lot.symbol,
            opened_at=lot.opened_at,
            original_quantity=lot.original_quantity,
            remaining_quantity=lot.remaining_quantity,
            total_cost_basis=lot.total_cost_basis,
            source_type=lot.source_type,
            realized_pnl=lot.realized_pnl,
            is_reward=lot.is_reward,
        )
        for lot in db.scalars(select(Lot).order_by(Lot.opened_at, Lot.id))
    ]


def _latest_prices_by_asset(db: Session, *, base_asset: str) -> dict[str, Decimal]:
    prices = {base_asset: ONE}
    symbols = db.scalars(
        select(Symbol)
        .where(Symbol.quote_asset_code == base_asset)
        .where(Symbol.base_asset_code.is_not(None))
    )
    for symbol in symbols:
        price = db.scalar(
            select(PriceSnapshot.price)
            .where(PriceSnapshot.symbol == symbol.symbol)
            .order_by(desc(PriceSnapshot.observed_at), desc(PriceSnapshot.id))
            .limit(1)
        )
        if price is not None and symbol.base_asset_code is not None:
            prices[symbol.base_asset_code] = price
    return prices


def _missing_price_assets(lots: list[LotState], prices: dict[str, Decimal]) -> list[str]:
    held_assets = {
        lot.asset_code
        for lot in lots
        if lot.remaining_quantity > ZERO and lot.asset_code not in prices
    }
    return sorted(held_assets)


def _base_asset_cash_flows(db: Session, base_asset: str) -> tuple[Decimal, Decimal]:
    deposits = sum(
        (
            deposit.amount
            for deposit in db.scalars(select(Deposit).where(Deposit.asset_code == base_asset))
        ),
        ZERO,
    )
    withdrawals = sum(
        (
            withdrawal.amount + withdrawal.transaction_fee
            for withdrawal in db.scalars(
                select(Withdrawal).where(Withdrawal.asset_code == base_asset)
            )
        ),
        ZERO,
    )
    return deposits, withdrawals


def _holdings_payload(symbol_pnl: dict[str, SymbolPnL], total_equity: Decimal) -> list[dict]:
    holdings = []
    for asset_code, item in sorted(symbol_pnl.items()):
        allocation = None if total_equity == ZERO else item.market_value / total_equity
        holdings.append(
            {
                "asset_code": asset_code,
                "quantity": decimal_to_string(item.quantity),
                "average_buy_price": None
                if item.average_buy_price is None
                else decimal_to_string(item.average_buy_price),
                "cost_basis": decimal_to_string(item.cost_basis),
                "market_value": decimal_to_string(item.market_value),
                "unrealized_pnl_including_rewards": decimal_to_string(
                    item.unrealized_pnl_including_rewards
                ),
                "unrealized_pnl_excluding_rewards": decimal_to_string(
                    item.unrealized_pnl_excluding_rewards
                ),
                "reward_quantity": decimal_to_string(item.reward_quantity),
                "reward_value": decimal_to_string(item.reward_value),
                "allocation_pct": None if allocation is None else decimal_to_string(allocation),
            }
        )
    return holdings


def _snapshot_window_chronological(db: Session, *, limit: int) -> list[PortfolioSnapshot]:
    snapshots = list(
        db.scalars(
            select(PortfolioSnapshot)
            .order_by(desc(PortfolioSnapshot.snapshot_at), desc(PortfolioSnapshot.id))
            .limit(limit)
        )
    )
    return list(reversed(snapshots))
