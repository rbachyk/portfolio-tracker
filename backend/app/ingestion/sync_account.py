from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.binance.client import BinanceClient
from app.db.models import SpotBalance, utc_now
from app.ingestion.binance_records import (
    deterministic_external_id,
    mark_sync_completed,
    mark_sync_failed,
    mark_sync_started,
    upsert_raw_event,
)

ZERO = Decimal("0")


def sync_account_info(db: Session, client: BinanceClient) -> int:
    sync_state = mark_sync_started(db, "sync_account_info")
    try:
        payload = client.get_account_info(omit_zero_balances=True)
        observed_at = utc_now()
        external_id = deterministic_external_id(
            "account_info",
            payload,
            ["updateTime", "makerCommission", "takerCommission"],
        )
        raw_event = upsert_raw_event(
            db,
            source="binance_spot",
            event_type="ACCOUNT_INFO",
            external_id=external_id,
            event_time=observed_at,
            payload=payload,
        )

        seen_assets: set[str] = set()
        upserted = 0
        for balance_payload in payload.get("balances", []):
            asset_code = str(balance_payload["asset"]).upper()
            free = Decimal(str(balance_payload.get("free", "0")))
            locked = Decimal(str(balance_payload.get("locked", "0")))
            total = free + locked
            seen_assets.add(asset_code)

            balance = db.scalar(select(SpotBalance).where(SpotBalance.asset_code == asset_code))
            if balance is None:
                balance = SpotBalance(asset_code=asset_code)
                db.add(balance)
                upserted += 1

            balance.raw_event_id = raw_event.id
            balance.free = free
            balance.locked = locked
            balance.total = total
            balance.snapshot_at = observed_at
            balance.updated_at = observed_at

        for balance in db.scalars(select(SpotBalance)).all():
            if balance.asset_code in seen_assets:
                continue
            balance.raw_event_id = raw_event.id
            balance.free = ZERO
            balance.locked = ZERO
            balance.total = ZERO
            balance.snapshot_at = observed_at
            balance.updated_at = observed_at

        mark_sync_completed(sync_state)
        db.commit()
        return upserted
    except Exception as exc:
        db.rollback()
        mark_sync_failed(db, "sync_account_info", str(exc))
        db.commit()
        raise
