from __future__ import annotations

from decimal import Decimal
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.binance.client import BinanceClient
from app.db.models import EarnPosition, EarnRedemption, EarnReward, EarnSubscription, utc_now
from app.ingestion.binance_records import (
    deterministic_external_id,
    mark_sync_completed,
    mark_sync_failed,
    mark_sync_started,
    parse_binance_time,
    upsert_raw_event,
)

DEFAULT_EARN_PAGE_SIZE = 100
EarnProductType = Literal["flexible", "locked"]


def sync_earn_positions(
    db: Session,
    client: BinanceClient,
    *,
    product_types: tuple[EarnProductType, ...] = ("flexible", "locked"),
    size: int = DEFAULT_EARN_PAGE_SIZE,
) -> int:
    sync_state = mark_sync_started(db, "sync_earn_positions")
    try:
        upserted = 0
        for product_type in product_types:
            upserted += _sync_position_type(db, client, product_type=product_type, size=size)

        mark_sync_completed(sync_state)
        db.commit()
        return upserted
    except Exception as exc:
        db.rollback()
        mark_sync_failed(db, "sync_earn_positions", str(exc))
        db.commit()
        raise


def sync_earn_subscriptions(
    db: Session,
    client: BinanceClient,
    *,
    start_time_ms: int,
    end_time_ms: int | None = None,
    product_types: tuple[EarnProductType, ...] = ("flexible", "locked"),
    size: int = DEFAULT_EARN_PAGE_SIZE,
) -> int:
    return _sync_earn_history(
        db,
        client,
        job_name="sync_earn_subscriptions",
        product_types=product_types,
        start_time_ms=start_time_ms,
        end_time_ms=end_time_ms,
        size=size,
        fetcher_name="get_simple_earn_subscription_records",
        upsert_record=_upsert_subscription,
    )


def sync_earn_redemptions(
    db: Session,
    client: BinanceClient,
    *,
    start_time_ms: int,
    end_time_ms: int | None = None,
    product_types: tuple[EarnProductType, ...] = ("flexible", "locked"),
    size: int = DEFAULT_EARN_PAGE_SIZE,
) -> int:
    return _sync_earn_history(
        db,
        client,
        job_name="sync_earn_redemptions",
        product_types=product_types,
        start_time_ms=start_time_ms,
        end_time_ms=end_time_ms,
        size=size,
        fetcher_name="get_simple_earn_redemption_records",
        upsert_record=_upsert_redemption,
    )


def sync_earn_rewards(
    db: Session,
    client: BinanceClient,
    *,
    start_time_ms: int,
    end_time_ms: int | None = None,
    product_types: tuple[EarnProductType, ...] = ("flexible", "locked"),
    size: int = DEFAULT_EARN_PAGE_SIZE,
) -> int:
    return _sync_earn_history(
        db,
        client,
        job_name="sync_earn_rewards",
        product_types=product_types,
        start_time_ms=start_time_ms,
        end_time_ms=end_time_ms,
        size=size,
        fetcher_name="get_simple_earn_rewards_history",
        upsert_record=_upsert_reward,
    )


def _sync_position_type(
    db: Session,
    client: BinanceClient,
    *,
    product_type: EarnProductType,
    size: int,
) -> int:
    current = 1
    upserted = 0
    while True:
        if product_type == "flexible":
            response = client.get_simple_earn_flexible_positions(current=current, size=size)
        else:
            response = client.get_simple_earn_locked_positions(current=current, size=size)

        rows = _response_rows(response)
        for payload in rows:
            upserted += _upsert_position(db, product_type, payload)
        if len(rows) < size:
            return upserted
        current += 1


def _sync_earn_history(
    db: Session,
    client: BinanceClient,
    *,
    job_name: str,
    product_types: tuple[EarnProductType, ...],
    start_time_ms: int,
    end_time_ms: int | None,
    size: int,
    fetcher_name: str,
    upsert_record,
) -> int:
    sync_state = mark_sync_started(db, job_name)
    try:
        inserted = 0
        for product_type in product_types:
            current = 1
            while True:
                response = getattr(client, fetcher_name)(
                    product_type=product_type,
                    start_time_ms=start_time_ms,
                    end_time_ms=end_time_ms,
                    current=current,
                    size=size,
                )
                rows = _response_rows(response)
                for payload in rows:
                    inserted += upsert_record(db, product_type, payload)
                if len(rows) < size:
                    break
                current += 1

        mark_sync_completed(sync_state)
        db.commit()
        return inserted
    except Exception as exc:
        db.rollback()
        mark_sync_failed(db, job_name, str(exc))
        db.commit()
        raise


def _upsert_position(db: Session, product_type: EarnProductType, payload: dict) -> int:
    external_id = deterministic_external_id(
        f"earn_position:{product_type}",
        payload,
        ["positionId", "productId", "projectId", "asset"],
    )
    asset_code = _asset_code(payload)
    raw_event = upsert_raw_event(
        db,
        source="binance_simple_earn",
        event_type="EARN_POSITION",
        external_id=external_id,
        symbol=asset_code,
        payload=payload,
    )
    position = db.scalar(select(EarnPosition).where(EarnPosition.external_id == external_id))
    if position is None:
        position = EarnPosition(external_id=external_id)
        db.add(position)
        inserted = 1
    else:
        inserted = 0

    position.raw_event_id = raw_event.id
    position.product_type = product_type
    position.product_id = _product_id(payload)
    position.asset_code = asset_code
    position.amount = _amount(payload, ["totalAmount", "amount", "principal"])
    position.auto_subscribe = payload.get("autoSubscribe")
    position.snapshot_at = utc_now()
    position.updated_at = utc_now()
    return inserted


def _upsert_subscription(db: Session, product_type: EarnProductType, payload: dict) -> int:
    external_id = deterministic_external_id(
        f"earn_subscription:{product_type}",
        payload,
        ["purchaseId", "subscriptionId", "time", "asset", "amount"],
    )
    raw_event = _upsert_earn_history_raw_event(
        product_type=product_type,
        event_type="EARN_SUBSCRIPTION",
        external_id=external_id,
        payload=payload,
        db=db,
    )
    subscription = db.scalar(
        select(EarnSubscription).where(EarnSubscription.external_id == external_id)
    )
    if subscription is None:
        subscription = EarnSubscription(external_id=external_id)
        db.add(subscription)
        inserted = 1
    else:
        inserted = 0

    subscription.raw_event_id = raw_event.id
    subscription.product_type = product_type
    subscription.purchase_id = _string_or_none(
        payload.get("purchaseId") or payload.get("subscriptionId")
    )
    subscription.product_id = _product_id(payload)
    subscription.asset_code = _asset_code(payload)
    subscription.amount = _amount(payload, ["amount", "purchaseAmount", "principal"])
    subscription.source_endpoint = f"simple-earn/{product_type}/subscriptionRecord"
    subscription.subscribed_at = _record_time(payload)
    subscription.updated_at = utc_now()
    return inserted


def _upsert_redemption(db: Session, product_type: EarnProductType, payload: dict) -> int:
    external_id = deterministic_external_id(
        f"earn_redemption:{product_type}",
        payload,
        ["redeemId", "redemptionId", "time", "asset", "amount"],
    )
    raw_event = _upsert_earn_history_raw_event(
        product_type=product_type,
        event_type="EARN_REDEMPTION",
        external_id=external_id,
        payload=payload,
        db=db,
    )
    redemption = db.scalar(select(EarnRedemption).where(EarnRedemption.external_id == external_id))
    if redemption is None:
        redemption = EarnRedemption(external_id=external_id)
        db.add(redemption)
        inserted = 1
    else:
        inserted = 0

    redemption.raw_event_id = raw_event.id
    redemption.product_type = product_type
    redemption.redeem_id = _string_or_none(payload.get("redeemId") or payload.get("redemptionId"))
    redemption.product_id = _product_id(payload)
    redemption.asset_code = _asset_code(payload)
    redemption.amount = _amount(payload, ["amount", "redeemAmount", "principal"])
    redemption.source_endpoint = f"simple-earn/{product_type}/redemptionRecord"
    redemption.redeemed_at = _record_time(payload)
    redemption.updated_at = utc_now()
    return inserted


def _upsert_reward(db: Session, product_type: EarnProductType, payload: dict) -> int:
    external_id = deterministic_external_id(
        f"earn_reward:{product_type}",
        payload,
        ["rewardId", "time", "asset", "rewards", "amount", "type"],
    )
    raw_event = _upsert_earn_history_raw_event(
        product_type=product_type,
        event_type="EARN_REWARD",
        external_id=external_id,
        payload=payload,
        db=db,
    )
    reward = db.scalar(select(EarnReward).where(EarnReward.external_id == external_id))
    if reward is None:
        reward = EarnReward(external_id=external_id)
        db.add(reward)
        inserted = 1
    else:
        inserted = 0

    reward.raw_event_id = raw_event.id
    reward.product_type = product_type
    reward.product_id = _product_id(payload)
    reward.asset_code = _asset_code(payload)
    reward.reward_type = _string_or_none(payload.get("type") or payload.get("rewardType"))
    reward.amount = _amount(payload, ["rewards", "reward", "amount"])
    reward.cost_basis_mode = "ZERO"
    reward.source_endpoint = f"simple-earn/{product_type}/rewardsRecord"
    reward.rewarded_at = _record_time(payload)
    reward.updated_at = utc_now()
    return inserted


def _upsert_earn_history_raw_event(
    *,
    db: Session,
    product_type: EarnProductType,
    event_type: str,
    external_id: str,
    payload: dict,
):
    return upsert_raw_event(
        db,
        source="binance_simple_earn",
        event_type=event_type,
        external_id=external_id,
        symbol=_asset_code(payload),
        event_time=_record_time(payload),
        payload={**payload, "_productType": product_type},
    )


def _response_rows(response: dict | list[dict]) -> list[dict]:
    if isinstance(response, list):
        return response
    rows = response.get("rows", [])
    if isinstance(rows, list):
        return rows
    return []


def _asset_code(payload: dict) -> str:
    return str(payload.get("asset") or payload.get("rewardAsset") or "").upper()


def _product_id(payload: dict) -> str | None:
    return _string_or_none(payload.get("productId") or payload.get("projectId"))


def _record_time(payload: dict):
    return parse_binance_time(
        payload.get("time") or payload.get("createTime") or payload.get("purchaseTime")
    )


def _amount(payload: dict, keys: list[str]) -> Decimal:
    for key in keys:
        if payload.get(key) not in (None, ""):
            return Decimal(str(payload[key]))
    return Decimal("0")


def _string_or_none(value: object | None) -> str | None:
    if value in (None, ""):
        return None
    return str(value)
