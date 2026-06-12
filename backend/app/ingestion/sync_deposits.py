from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.binance.client import BinanceClient
from app.db.models import Deposit, Withdrawal, utc_now
from app.ingestion.binance_records import (
    deterministic_external_id,
    mark_sync_completed,
    mark_sync_failed,
    mark_sync_started,
    parse_binance_time,
    upsert_raw_event,
)

DEFAULT_HISTORY_LIMIT = 1000


def sync_deposits(
    db: Session,
    client: BinanceClient,
    *,
    start_time_ms: int,
    end_time_ms: int | None = None,
    coin: str | None = None,
    limit: int = DEFAULT_HISTORY_LIMIT,
) -> int:
    sync_state = mark_sync_started(db, "sync_deposits")
    try:
        inserted = 0
        offset = 0
        while True:
            payloads = client.get_deposit_history(
                coin=coin,
                start_time_ms=start_time_ms,
                end_time_ms=end_time_ms,
                offset=offset,
                limit=limit,
            )
            for payload in payloads:
                inserted += _upsert_deposit(db, payload)
            if len(payloads) < limit:
                break
            offset += limit

        mark_sync_completed(sync_state)
        db.commit()
        return inserted
    except Exception as exc:
        db.rollback()
        mark_sync_failed(db, "sync_deposits", str(exc))
        db.commit()
        raise


def sync_withdrawals(
    db: Session,
    client: BinanceClient,
    *,
    start_time_ms: int,
    end_time_ms: int | None = None,
    coin: str | None = None,
    limit: int = DEFAULT_HISTORY_LIMIT,
) -> int:
    sync_state = mark_sync_started(db, "sync_withdrawals")
    try:
        inserted = 0
        offset = 0
        while True:
            payloads = client.get_withdraw_history(
                coin=coin,
                start_time_ms=start_time_ms,
                end_time_ms=end_time_ms,
                offset=offset,
                limit=limit,
            )
            for payload in payloads:
                inserted += _upsert_withdrawal(db, payload)
            if len(payloads) < limit:
                break
            offset += limit

        mark_sync_completed(sync_state)
        db.commit()
        return inserted
    except Exception as exc:
        db.rollback()
        mark_sync_failed(db, "sync_withdrawals", str(exc))
        db.commit()
        raise


def _upsert_deposit(db: Session, payload: dict) -> int:
    external_id = deterministic_external_id("deposit", payload, ["id", "txId", "insertTime"])
    raw_event = upsert_raw_event(
        db,
        source="binance_wallet",
        event_type="DEPOSIT",
        external_id=external_id,
        symbol=payload.get("coin"),
        event_time=parse_binance_time(payload.get("completeTime") or payload.get("insertTime")),
        payload=payload,
    )
    deposit = db.scalar(select(Deposit).where(Deposit.external_id == external_id))
    if deposit is None:
        deposit = Deposit(external_id=external_id)
        db.add(deposit)
        inserted = 1
    else:
        inserted = 0

    deposit.raw_event_id = raw_event.id
    deposit.asset_code = payload["coin"]
    deposit.amount = Decimal(str(payload["amount"]))
    deposit.network = payload.get("network")
    deposit.status = _optional_int(payload.get("status"))
    deposit.address = payload.get("address")
    deposit.address_tag = payload.get("addressTag")
    deposit.tx_id = payload.get("txId")
    deposit.transfer_type = _optional_int(payload.get("transferType"))
    deposit.wallet_type = _optional_int(payload.get("walletType"))
    deposit.inserted_at = parse_binance_time(payload.get("insertTime"))
    deposit.completed_at = parse_binance_time(payload.get("completeTime"))
    deposit.updated_at = utc_now()
    return inserted


def _upsert_withdrawal(db: Session, payload: dict) -> int:
    external_id = deterministic_external_id("withdrawal", payload, ["id", "txId", "applyTime"])
    raw_event = upsert_raw_event(
        db,
        source="binance_wallet",
        event_type="WITHDRAWAL",
        external_id=external_id,
        symbol=payload.get("coin"),
        event_time=parse_binance_time(payload.get("completeTime") or payload.get("applyTime")),
        payload=payload,
    )
    withdrawal = db.scalar(select(Withdrawal).where(Withdrawal.external_id == external_id))
    if withdrawal is None:
        withdrawal = Withdrawal(external_id=external_id)
        db.add(withdrawal)
        inserted = 1
    else:
        inserted = 0

    withdrawal.raw_event_id = raw_event.id
    withdrawal.asset_code = payload["coin"]
    withdrawal.amount = Decimal(str(payload["amount"]))
    withdrawal.transaction_fee = Decimal(str(payload.get("transactionFee", "0")))
    withdrawal.network = payload.get("network")
    withdrawal.status = _optional_int(payload.get("status"))
    withdrawal.address = payload.get("address")
    withdrawal.tx_id = payload.get("txId")
    withdrawal.withdraw_order_id = payload.get("withdrawOrderId")
    withdrawal.transfer_type = _optional_int(payload.get("transferType"))
    withdrawal.wallet_type = _optional_int(payload.get("walletType"))
    withdrawal.applied_at = parse_binance_time(payload.get("applyTime"))
    withdrawal.completed_at = parse_binance_time(payload.get("completeTime"))
    withdrawal.updated_at = utc_now()
    return inserted


def _optional_int(value: object | None) -> int | None:
    if value in (None, ""):
        return None
    return int(value)
