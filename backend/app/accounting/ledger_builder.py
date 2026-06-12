from __future__ import annotations

from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.accounting.events import AccountingEvent
from app.accounting.lots import LotState, rebuild_lots_from_events
from app.db.models import (
    Deposit,
    EarnRedemption,
    EarnReward,
    EarnSubscription,
    LedgerEvent,
    Lot,
    Trade,
    Withdrawal,
    utc_now,
)

ZERO = Decimal("0")


def build_ledger_events(db: Session) -> int:
    events = build_accounting_events_from_db(db)
    upserted = 0
    for event in events:
        upserted += upsert_ledger_event(db, event)
    db.commit()
    return upserted


def rebuild_lots(db: Session) -> int:
    events = [
        ledger_event_to_accounting_event(event)
        for event in db.scalars(
            select(LedgerEvent).order_by(LedgerEvent.event_time, LedgerEvent.id)
        )
    ]
    result = rebuild_lots_from_events(events)
    db.execute(delete(Lot))
    for lot in result.lots:
        db.add(_lot_state_to_model(db, lot))
    db.commit()
    return len(result.lots)


def build_accounting_events_from_db(db: Session) -> list[AccountingEvent]:
    events: list[AccountingEvent] = []
    for trade in db.scalars(select(Trade).order_by(Trade.executed_at, Trade.id)):
        events.extend(trade_to_ledger_events(trade))
    for deposit in db.scalars(select(Deposit).order_by(Deposit.completed_at, Deposit.id)):
        events.append(deposit_to_ledger_event(deposit))
    for withdrawal in db.scalars(
        select(Withdrawal).order_by(Withdrawal.completed_at, Withdrawal.id)
    ):
        events.append(withdrawal_to_ledger_event(withdrawal))
    for subscription in db.scalars(
        select(EarnSubscription).order_by(EarnSubscription.subscribed_at, EarnSubscription.id)
    ):
        events.append(earn_subscription_to_ledger_event(subscription))
    for redemption in db.scalars(
        select(EarnRedemption).order_by(EarnRedemption.redeemed_at, EarnRedemption.id)
    ):
        events.append(earn_redemption_to_ledger_event(redemption))
    for reward in db.scalars(select(EarnReward).order_by(EarnReward.rewarded_at, EarnReward.id)):
        events.append(earn_reward_to_ledger_event(reward))
    return sorted(events, key=lambda event: (event.event_time, event.external_id))


def trade_to_ledger_events(trade: Trade) -> list[AccountingEvent]:
    if trade.side == "BUY":
        quantity = trade.quantity
        cost_basis = trade.quote_quantity
        if trade.fee_asset_code == trade.base_asset_code:
            quantity -= trade.fee_amount
        elif trade.fee_asset_code == trade.quote_asset_code:
            cost_basis += trade.fee_amount

        events = [
            AccountingEvent(
                event_type="SPOT_BUY",
                external_id=f"trade:{trade.id}:buy",
                source_table="trades",
                source_id=trade.id,
                symbol=trade.symbol,
                asset_code=trade.base_asset_code,
                quote_asset_code=trade.quote_asset_code,
                quantity=quantity,
                quote_quantity=cost_basis,
                unit_price=cost_basis / quantity,
                fee_asset_code=trade.fee_asset_code,
                fee_amount=trade.fee_amount,
                event_time=trade.executed_at,
                metadata={"binance_trade_id": trade.binance_trade_id},
            )
        ]
    else:
        quantity = trade.quantity
        proceeds = trade.quote_quantity
        if trade.fee_asset_code == trade.base_asset_code:
            quantity += trade.fee_amount
        elif trade.fee_asset_code == trade.quote_asset_code:
            proceeds -= trade.fee_amount

        events = [
            AccountingEvent(
                event_type="SPOT_SELL",
                external_id=f"trade:{trade.id}:sell",
                source_table="trades",
                source_id=trade.id,
                symbol=trade.symbol,
                asset_code=trade.base_asset_code,
                quote_asset_code=trade.quote_asset_code,
                quantity=-quantity,
                quote_quantity=proceeds,
                unit_price=proceeds / quantity,
                fee_asset_code=trade.fee_asset_code,
                fee_amount=trade.fee_amount,
                event_time=trade.executed_at,
                metadata={"binance_trade_id": trade.binance_trade_id},
            )
        ]

    if trade.fee_asset_code and trade.fee_amount > ZERO:
        events.append(
            AccountingEvent(
                event_type="TRADE_FEE",
                external_id=f"trade:{trade.id}:fee",
                source_table="trades",
                source_id=trade.id,
                symbol=trade.symbol,
                asset_code=trade.fee_asset_code,
                quantity=-trade.fee_amount,
                quote_quantity=ZERO,
                fee_asset_code=trade.fee_asset_code,
                fee_amount=trade.fee_amount,
                event_time=trade.executed_at,
                metadata={"binance_trade_id": trade.binance_trade_id},
            )
        )

    return events


def deposit_to_ledger_event(deposit: Deposit) -> AccountingEvent:
    return AccountingEvent(
        event_type="DEPOSIT",
        external_id=f"deposit:{deposit.id}",
        source_table="deposits",
        source_id=deposit.id,
        asset_code=deposit.asset_code,
        quantity=deposit.amount,
        quote_quantity=ZERO,
        event_time=deposit.completed_at or deposit.inserted_at or deposit.created_at,
    )


def withdrawal_to_ledger_event(withdrawal: Withdrawal) -> AccountingEvent:
    return AccountingEvent(
        event_type="WITHDRAWAL",
        external_id=f"withdrawal:{withdrawal.id}",
        source_table="withdrawals",
        source_id=withdrawal.id,
        asset_code=withdrawal.asset_code,
        quantity=-(withdrawal.amount + withdrawal.transaction_fee),
        quote_quantity=ZERO,
        fee_asset_code=withdrawal.asset_code,
        fee_amount=withdrawal.transaction_fee,
        event_time=withdrawal.completed_at or withdrawal.applied_at or withdrawal.created_at,
    )


def earn_subscription_to_ledger_event(subscription: EarnSubscription) -> AccountingEvent:
    return AccountingEvent(
        event_type="EARN_SUBSCRIPTION",
        external_id=f"earn_subscription:{subscription.id}",
        source_table="earn_subscriptions",
        source_id=subscription.id,
        asset_code=subscription.asset_code,
        quantity=ZERO,
        quote_quantity=ZERO,
        event_time=subscription.subscribed_at or subscription.created_at,
    )


def earn_redemption_to_ledger_event(redemption: EarnRedemption) -> AccountingEvent:
    return AccountingEvent(
        event_type="EARN_REDEMPTION",
        external_id=f"earn_redemption:{redemption.id}",
        source_table="earn_redemptions",
        source_id=redemption.id,
        asset_code=redemption.asset_code,
        quantity=ZERO,
        quote_quantity=ZERO,
        event_time=redemption.redeemed_at or redemption.created_at,
    )


def earn_reward_to_ledger_event(reward: EarnReward) -> AccountingEvent:
    return AccountingEvent(
        event_type="EARN_REWARD",
        external_id=f"earn_reward:{reward.id}",
        source_table="earn_rewards",
        source_id=reward.id,
        asset_code=reward.asset_code,
        quantity=reward.amount,
        quote_quantity=ZERO,
        event_time=reward.rewarded_at or reward.created_at,
        metadata={"cost_basis_mode": reward.cost_basis_mode},
    )


def upsert_ledger_event(db: Session, event: AccountingEvent) -> int:
    ledger_event = db.scalar(
        select(LedgerEvent).where(LedgerEvent.external_id == event.external_id)
    )
    if ledger_event is None:
        ledger_event = LedgerEvent(external_id=event.external_id)
        db.add(ledger_event)
        inserted = 1
    else:
        inserted = 0

    ledger_event.event_type = event.event_type
    ledger_event.source_table = event.source_table
    ledger_event.source_id = event.source_id
    ledger_event.symbol = event.symbol
    ledger_event.asset_code = event.asset_code
    ledger_event.quote_asset_code = event.quote_asset_code
    ledger_event.quantity = event.quantity
    ledger_event.quote_quantity = event.quote_quantity
    ledger_event.unit_price = event.unit_price
    ledger_event.fee_asset_code = event.fee_asset_code
    ledger_event.fee_amount = event.fee_amount
    ledger_event.event_time = event.event_time
    ledger_event.event_metadata = event.metadata
    ledger_event.updated_at = utc_now()
    return inserted


def ledger_event_to_accounting_event(ledger_event: LedgerEvent) -> AccountingEvent:
    return AccountingEvent(
        event_type=ledger_event.event_type,
        external_id=ledger_event.external_id,
        source_table=ledger_event.source_table,
        source_id=ledger_event.source_id,
        symbol=ledger_event.symbol,
        asset_code=ledger_event.asset_code,
        quote_asset_code=ledger_event.quote_asset_code,
        quantity=ledger_event.quantity,
        quote_quantity=ledger_event.quote_quantity,
        unit_price=ledger_event.unit_price,
        fee_asset_code=ledger_event.fee_asset_code,
        fee_amount=ledger_event.fee_amount,
        event_time=ledger_event.event_time,
        metadata=ledger_event.event_metadata or {},
    )


def _lot_state_to_model(db: Session, lot: LotState) -> Lot:
    ledger_event = db.scalar(
        select(LedgerEvent).where(LedgerEvent.external_id == lot.source_event_id)
    )
    if ledger_event is None:
        raise ValueError(f"Missing ledger event for lot {lot.source_event_id}")

    return Lot(
        source_ledger_event_id=ledger_event.id,
        asset_code=lot.asset_code,
        symbol=lot.symbol,
        source_type=lot.source_type,
        opened_at=lot.opened_at,
        original_quantity=lot.original_quantity,
        remaining_quantity=lot.remaining_quantity,
        unit_cost=lot.unit_cost,
        total_cost_basis=lot.total_cost_basis,
        realized_pnl=lot.realized_pnl,
        is_reward=lot.is_reward,
    )
