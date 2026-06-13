from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.accounting.lots import LotState
from app.accounting.pnl import calculate_lot_pnl, calculate_symbol_pnl
from app.db.models import (
    Deposit,
    EarnPosition,
    EarnRedemption,
    EarnReward,
    EarnSubscription,
    FundingTransfer,
    LedgerEvent,
    Lot,
    P2POrder,
    PortfolioSnapshot,
    PriceSnapshot,
    SpotBalance,
    Symbol,
    SyncState,
    TargetAllocation,
    Trade,
    Withdrawal,
)
from app.services.asset_utils import is_binance_earn_wrapper_asset
from app.services.portfolio_service import decimal_to_string, portfolio_snapshot_to_dict

ZERO = Decimal("0")
ONE = Decimal("1")


def get_overview(db: Session, *, base_asset: str) -> dict:
    snapshots = list(
        db.scalars(
            select(PortfolioSnapshot)
            .order_by(desc(PortfolioSnapshot.snapshot_at), desc(PortfolioSnapshot.id))
            .limit(2)
        )
    )
    latest = snapshots[0] if snapshots else None
    previous = snapshots[1] if len(snapshots) > 1 else None
    last_sync = _last_sync_time(db)

    if latest is None:
        return {
            "snapshot": None,
            "total_equity": "0",
            "total_deposited_capital": "0",
            "total_pnl": "0",
            "total_pnl_pct": None,
            "change_24h": None,
            "earn_rewards_total_value": "0",
            "asset_count": 0,
            "last_sync_time": last_sync,
        }

    total_pnl = latest.total_equity - latest.net_deposited
    change_24h = None if previous is None else latest.total_equity - previous.total_equity
    return {
        "snapshot": portfolio_snapshot_to_dict(latest),
        "total_equity": decimal_to_string(latest.total_equity),
        "total_deposited_capital": decimal_to_string(latest.net_deposited),
        "total_pnl": decimal_to_string(total_pnl),
        "total_pnl_pct": None
        if latest.net_deposited == ZERO
        else decimal_to_string(total_pnl / latest.net_deposited),
        "change_24h": None if change_24h is None else decimal_to_string(change_24h),
        "earn_rewards_total_value": decimal_to_string(latest.earn_rewards_value),
        "asset_count": latest.asset_count,
        "last_sync_time": last_sync,
    }


def list_holdings(db: Session, *, base_asset: str) -> list[dict]:
    base_asset = base_asset.strip().upper()
    lots = _load_lot_states(db)
    current_prices = _latest_prices_by_asset(db, base_asset=base_asset)
    pnl_by_asset = calculate_symbol_pnl(
        [lot for lot in lots if lot.asset_code in current_prices],
        current_prices=current_prices,
    )
    spot_quantities = _spot_quantities(db)
    earn_quantities = _earn_quantities(db)
    targets = _target_allocations(db)
    asset_codes = sorted(
        set(pnl_by_asset) | set(spot_quantities) | set(earn_quantities) | set(targets)
    )

    rows = []
    total_market_value = ZERO
    for asset_code in asset_codes:
        current_price = current_prices.get(asset_code)
        spot_quantity = spot_quantities.get(asset_code, ZERO)
        earn_quantity = earn_quantities.get(asset_code, ZERO)
        pnl = pnl_by_asset.get(asset_code)
        accounting_quantity = ZERO if pnl is None else pnl.quantity
        has_balance_quantity = asset_code in spot_quantities or asset_code in earn_quantities
        total_quantity = (
            spot_quantity + earn_quantity if has_balance_quantity else accounting_quantity
        )
        market_value = ZERO if current_price is None else total_quantity * current_price
        total_market_value += market_value
        rows.append(
            {
                "asset_code": asset_code,
                "total_quantity": decimal_to_string(total_quantity),
                "spot_quantity": decimal_to_string(spot_quantity),
                "earn_quantity": decimal_to_string(earn_quantity),
                "accounting_quantity": decimal_to_string(accounting_quantity),
                "average_buy_price": None
                if pnl is None or pnl.average_buy_price is None
                else decimal_to_string(pnl.average_buy_price),
                "current_price": None
                if current_price is None
                else decimal_to_string(current_price),
                "cost_basis": decimal_to_string(ZERO if pnl is None else pnl.cost_basis),
                "market_value": decimal_to_string(market_value),
                "unrealized_pnl_including_rewards": decimal_to_string(
                    ZERO if pnl is None else pnl.unrealized_pnl_including_rewards
                ),
                "unrealized_pnl_excluding_rewards": decimal_to_string(
                    ZERO if pnl is None else pnl.unrealized_pnl_excluding_rewards
                ),
                "unrealized_pnl_pct": _pnl_pct(pnl),
                "earn_rewards_quantity": decimal_to_string(
                    ZERO if pnl is None else pnl.reward_quantity
                ),
                "earn_rewards_value": decimal_to_string(ZERO if pnl is None else pnl.reward_value),
                "allocation_pct": "0",
                "target_pct": None
                if asset_code not in targets
                else decimal_to_string(targets[asset_code]),
                "target_difference_pct": None,
            }
        )

    for row in rows:
        market_value = Decimal(row["market_value"])
        allocation_pct = ZERO if total_market_value == ZERO else market_value / total_market_value
        row["allocation_pct"] = decimal_to_string(allocation_pct)
        if row["target_pct"] is not None:
            row["target_difference_pct"] = decimal_to_string(
                allocation_pct - Decimal(row["target_pct"])
            )

    return sorted(rows, key=lambda item: Decimal(item["market_value"]), reverse=True)


def list_lots(db: Session, *, base_asset: str, include_closed: bool = False) -> list[dict]:
    current_prices = _latest_prices_by_asset(db, base_asset=base_asset.strip().upper())
    rows = []
    lots = db.scalars(select(Lot).order_by(Lot.opened_at, Lot.id)).all()
    for lot in lots:
        if not include_closed and lot.remaining_quantity <= ZERO:
            continue
        current_price = current_prices.get(lot.asset_code)
        lot_state = _lot_model_to_state(lot)
        lot_pnl = None if current_price is None else calculate_lot_pnl(lot_state, current_price)
        ledger_event = db.get(LedgerEvent, lot.source_ledger_event_id)
        source_trade = _source_trade(db, ledger_event)
        rows.append(
            {
                "id": lot.id,
                "asset_code": lot.asset_code,
                "symbol": lot.symbol,
                "buy_date": lot.opened_at.isoformat(),
                "quantity_bought": decimal_to_string(lot.original_quantity),
                "remaining_quantity": decimal_to_string(lot.remaining_quantity),
                "buy_price": decimal_to_string(lot.unit_cost),
                "current_price": None
                if current_price is None
                else decimal_to_string(current_price),
                "cost_basis": decimal_to_string(lot.remaining_quantity * lot.unit_cost),
                "current_value": None
                if lot_pnl is None
                else decimal_to_string(lot_pnl.market_value),
                "unrealized_pnl": None
                if lot_pnl is None
                else decimal_to_string(lot_pnl.unrealized_pnl),
                "unrealized_pnl_pct": None
                if lot_pnl is None or lot_pnl.unrealized_pnl_pct is None
                else decimal_to_string(lot_pnl.unrealized_pnl_pct),
                "realized_pnl": decimal_to_string(lot.realized_pnl),
                "source_type": lot.source_type,
                "source_trade_id": source_trade["binance_trade_id"],
                "source_order_id": source_trade["binance_order_id"],
                "fee": source_trade["fee"],
                "is_reward": lot.is_reward,
            }
        )
    return rows


def get_earn_dashboard(db: Session, *, base_asset: str) -> dict:
    current_prices = _latest_prices_by_asset(db, base_asset=base_asset.strip().upper())
    positions = [
        _earn_position_to_dict(position, current_prices) for position in _earn_positions(db)
    ]
    rewards = list(
        db.scalars(
            select(EarnReward).order_by(desc(EarnReward.rewarded_at), desc(EarnReward.id))
        )
    )
    reward_totals: dict[str, Decimal] = defaultdict(Decimal)
    rewards_over_time: dict[date, Decimal] = defaultdict(Decimal)
    for reward in rewards:
        reward_totals[reward.asset_code] += reward.amount
        if reward.rewarded_at is not None:
            price = current_prices.get(reward.asset_code, ZERO)
            rewards_over_time[reward.rewarded_at.date()] += reward.amount * price

    return {
        "positions": positions,
        "reward_totals": [
            {
                "asset_code": asset,
                "quantity": decimal_to_string(quantity),
                "value": decimal_to_string(quantity * current_prices.get(asset, ZERO)),
            }
            for asset, quantity in sorted(reward_totals.items())
        ],
        "rewards_over_time": [
            {"date": day.isoformat(), "value": decimal_to_string(value)}
            for day, value in sorted(rewards_over_time.items())
        ],
        "rewards": [_earn_reward_to_dict(reward, current_prices) for reward in rewards[:500]],
        "subscriptions": [
            _earn_subscription_to_dict(item)
            for item in db.scalars(
                select(EarnSubscription).order_by(
                    desc(EarnSubscription.subscribed_at), desc(EarnSubscription.id)
                )
            ).all()
        ],
        "redemptions": [
            _earn_redemption_to_dict(item)
            for item in db.scalars(
                select(EarnRedemption).order_by(
                    desc(EarnRedemption.redeemed_at), desc(EarnRedemption.id)
                )
            ).all()
        ],
    }


def get_cash_flows(db: Session) -> dict:
    deposits = list(
        db.scalars(select(Deposit).order_by(desc(Deposit.completed_at), desc(Deposit.id)))
    )
    withdrawals = list(
        db.scalars(select(Withdrawal).order_by(desc(Withdrawal.completed_at), desc(Withdrawal.id)))
    )
    deposits_over_time: dict[date, Decimal] = defaultdict(Decimal)
    for deposit in deposits:
        event_time = deposit.completed_at or deposit.inserted_at or deposit.created_at
        deposits_over_time[event_time.date()] += deposit.amount
    for order in db.scalars(select(P2POrder).where(P2POrder.order_status == "COMPLETED")):
        if order.order_created_at is None:
            continue
        signed_amount = order.amount if order.trade_type == "BUY" else -order.amount
        deposits_over_time[order.order_created_at.date()] += signed_amount

    return {
        "deposits": [_deposit_to_dict(deposit) for deposit in deposits],
        "withdrawals": [_withdrawal_to_dict(withdrawal) for withdrawal in withdrawals],
        "p2p_orders": [
            _p2p_order_to_dict(order)
            for order in db.scalars(
                select(P2POrder).order_by(desc(P2POrder.order_created_at), desc(P2POrder.id))
            )
        ],
        "funding_transfers": [
            _funding_transfer_to_dict(transfer)
            for transfer in db.scalars(
                select(FundingTransfer).order_by(
                    desc(FundingTransfer.transferred_at), desc(FundingTransfer.id)
                )
            )
        ],
        "deposits_over_time": [
            {"date": day.isoformat(), "amount": decimal_to_string(amount)}
            for day, amount in sorted(deposits_over_time.items())
        ],
    }


def list_symbols(db: Session) -> list[dict]:
    return [
        {
            "symbol": symbol.symbol,
            "base_asset_code": symbol.base_asset_code,
            "quote_asset_code": symbol.quote_asset_code,
            "status": symbol.status,
            "is_spot_trading_allowed": symbol.is_spot_trading_allowed,
            "is_enabled": symbol.is_enabled,
        }
        for symbol in db.scalars(select(Symbol).order_by(Symbol.symbol))
    ]


def list_sync_states(db: Session) -> list[dict]:
    return [
        {
            "job_name": state.job_name,
            "status": state.status,
            "last_started_at": None
            if state.last_started_at is None
            else state.last_started_at.isoformat(),
            "last_completed_at": None
            if state.last_completed_at is None
            else state.last_completed_at.isoformat(),
            "error_message": state.error_message,
            "progress_current": state.progress_current,
            "progress_total": state.progress_total,
            "progress_message": state.progress_message,
            "updated_at": state.updated_at.isoformat(),
        }
        for state in db.scalars(select(SyncState).order_by(SyncState.job_name))
    ]


def _load_lot_states(db: Session) -> list[LotState]:
    return [
        _lot_model_to_state(lot)
        for lot in db.scalars(select(Lot).order_by(Lot.opened_at, Lot.id))
    ]


def _lot_model_to_state(lot: Lot) -> LotState:
    return LotState(
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


def _spot_quantities(db: Session) -> dict[str, Decimal]:
    return {
        balance.asset_code: balance.total
        for balance in db.scalars(select(SpotBalance))
        if balance.total > ZERO and not is_binance_earn_wrapper_asset(balance.asset_code)
    }


def _earn_quantities(db: Session) -> dict[str, Decimal]:
    totals: dict[str, Decimal] = defaultdict(Decimal)
    for position in _earn_positions(db):
        totals[position.asset_code] += position.amount
    return dict(totals)


def _earn_positions(db: Session) -> list[EarnPosition]:
    return list(
        db.scalars(
            select(EarnPosition).where(EarnPosition.amount > ZERO).order_by(EarnPosition.asset_code)
        )
    )


def _target_allocations(db: Session) -> dict[str, Decimal]:
    return {
        target.asset_code: target.target_pct
        for target in db.scalars(
            select(TargetAllocation).where(TargetAllocation.is_enabled.is_(True))
        )
    }


def _source_trade(db: Session, ledger_event: LedgerEvent | None) -> dict:
    if ledger_event is None or ledger_event.source_table != "trades":
        return {"binance_trade_id": None, "binance_order_id": None, "fee": None}
    trade = db.get(Trade, ledger_event.source_id)
    if trade is None:
        return {"binance_trade_id": None, "binance_order_id": None, "fee": None}
    return {
        "binance_trade_id": str(trade.binance_trade_id),
        "binance_order_id": str(trade.binance_order_id),
        "fee": None
        if trade.fee_asset_code is None
        else {
            "asset_code": trade.fee_asset_code,
            "amount": decimal_to_string(trade.fee_amount),
        },
    }


def _earn_position_to_dict(position: EarnPosition, prices: dict[str, Decimal]) -> dict:
    price = prices.get(position.asset_code)
    return {
        "asset_code": position.asset_code,
        "product_type": position.product_type,
        "product_id": position.product_id,
        "amount": decimal_to_string(position.amount),
        "auto_subscribe": position.auto_subscribe,
        "value": None if price is None else decimal_to_string(position.amount * price),
        "snapshot_at": position.snapshot_at.isoformat(),
    }


def _earn_reward_to_dict(reward: EarnReward, prices: dict[str, Decimal]) -> dict:
    price = prices.get(reward.asset_code)
    return {
        "asset_code": reward.asset_code,
        "product_type": reward.product_type,
        "product_id": reward.product_id,
        "reward_type": reward.reward_type,
        "amount": decimal_to_string(reward.amount),
        "value": None if price is None else decimal_to_string(reward.amount * price),
        "rewarded_at": None if reward.rewarded_at is None else reward.rewarded_at.isoformat(),
        "source_endpoint": reward.source_endpoint,
        "cost_basis_mode": reward.cost_basis_mode,
    }


def _earn_subscription_to_dict(subscription: EarnSubscription) -> dict:
    return {
        "asset_code": subscription.asset_code,
        "product_type": subscription.product_type,
        "product_id": subscription.product_id,
        "amount": decimal_to_string(subscription.amount),
        "subscribed_at": None
        if subscription.subscribed_at is None
        else subscription.subscribed_at.isoformat(),
        "source_endpoint": subscription.source_endpoint,
    }


def _earn_redemption_to_dict(redemption: EarnRedemption) -> dict:
    return {
        "asset_code": redemption.asset_code,
        "product_type": redemption.product_type,
        "product_id": redemption.product_id,
        "amount": decimal_to_string(redemption.amount),
        "redeemed_at": None
        if redemption.redeemed_at is None
        else redemption.redeemed_at.isoformat(),
        "source_endpoint": redemption.source_endpoint,
    }


def _deposit_to_dict(deposit: Deposit) -> dict:
    return {
        "asset_code": deposit.asset_code,
        "amount": decimal_to_string(deposit.amount),
        "network": deposit.network,
        "status": deposit.status,
        "tx_id": deposit.tx_id,
        "inserted_at": None if deposit.inserted_at is None else deposit.inserted_at.isoformat(),
        "completed_at": None if deposit.completed_at is None else deposit.completed_at.isoformat(),
    }


def _withdrawal_to_dict(withdrawal: Withdrawal) -> dict:
    return {
        "asset_code": withdrawal.asset_code,
        "amount": decimal_to_string(withdrawal.amount),
        "transaction_fee": decimal_to_string(withdrawal.transaction_fee),
        "network": withdrawal.network,
        "status": withdrawal.status,
        "tx_id": withdrawal.tx_id,
        "applied_at": None if withdrawal.applied_at is None else withdrawal.applied_at.isoformat(),
        "completed_at": None
        if withdrawal.completed_at is None
        else withdrawal.completed_at.isoformat(),
    }


def _p2p_order_to_dict(order: P2POrder) -> dict:
    return {
        "order_number": order.order_number,
        "trade_type": order.trade_type,
        "asset_code": order.asset_code,
        "fiat_code": order.fiat_code,
        "amount": decimal_to_string(order.amount),
        "total_price": decimal_to_string(order.total_price),
        "unit_price": None if order.unit_price is None else decimal_to_string(order.unit_price),
        "commission": decimal_to_string(order.commission),
        "order_status": order.order_status,
        "pay_method_name": order.pay_method_name,
        "order_created_at": None
        if order.order_created_at is None
        else order.order_created_at.isoformat(),
    }


def _funding_transfer_to_dict(transfer: FundingTransfer) -> dict:
    return {
        "tran_id": str(transfer.tran_id),
        "transfer_type": transfer.transfer_type,
        "asset_code": transfer.asset_code,
        "amount": decimal_to_string(transfer.amount),
        "status": transfer.status,
        "transferred_at": None
        if transfer.transferred_at is None
        else transfer.transferred_at.isoformat(),
    }


def _last_sync_time(db: Session) -> str | None:
    last_completed_at = db.scalar(
        select(SyncState.last_completed_at)
        .where(SyncState.last_completed_at.is_not(None))
        .order_by(desc(SyncState.last_completed_at))
        .limit(1)
    )
    return None if last_completed_at is None else last_completed_at.isoformat()


def _pnl_pct(pnl) -> str | None:
    if pnl is None or pnl.cost_basis == ZERO:
        return None
    return decimal_to_string(pnl.unrealized_pnl_including_rewards / pnl.cost_basis)
