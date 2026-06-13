from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.binance.client import BinanceClient
from app.db.models import FundingTransfer, P2POrder, utc_now
from app.ingestion.binance_records import (
    deterministic_external_id,
    mark_sync_completed,
    mark_sync_failed,
    mark_sync_started,
    parse_binance_time,
    upsert_raw_event,
)

DEFAULT_PAGE_SIZE = 100
P2P_TRADE_TYPES = ("BUY", "SELL")
FUNDING_TRANSFER_TYPES = ("FUNDING_MAIN", "MAIN_FUNDING")


def sync_p2p_orders(
    db: Session,
    client: BinanceClient,
    *,
    start_time_ms: int,
    end_time_ms: int | None = None,
    trade_types: tuple[str, ...] = P2P_TRADE_TYPES,
    rows: int = DEFAULT_PAGE_SIZE,
) -> int:
    sync_state = mark_sync_started(db, "sync_p2p_orders")
    try:
        inserted = 0
        for trade_type in trade_types:
            page = 1
            while True:
                response = client.get_c2c_order_history(
                    trade_type=trade_type,
                    start_timestamp_ms=start_time_ms,
                    end_timestamp_ms=end_time_ms,
                    page=page,
                    rows=rows,
                )
                payloads = _response_rows(response)
                for payload in payloads:
                    inserted += _upsert_p2p_order(db, payload)
                if len(payloads) < rows:
                    break
                page += 1

        mark_sync_completed(sync_state)
        db.commit()
        return inserted
    except Exception as exc:
        db.rollback()
        mark_sync_failed(db, "sync_p2p_orders", str(exc))
        db.commit()
        raise


def sync_funding_transfers(
    db: Session,
    client: BinanceClient,
    *,
    start_time_ms: int,
    end_time_ms: int | None = None,
    transfer_types: tuple[str, ...] = FUNDING_TRANSFER_TYPES,
    size: int = DEFAULT_PAGE_SIZE,
) -> int:
    sync_state = mark_sync_started(db, "sync_funding_transfers")
    try:
        inserted = 0
        for transfer_type in transfer_types:
            current = 1
            while True:
                response = client.get_universal_transfer_history(
                    transfer_type=transfer_type,
                    start_time_ms=start_time_ms,
                    end_time_ms=end_time_ms,
                    current=current,
                    size=size,
                )
                payloads = _response_rows(response)
                for payload in payloads:
                    inserted += _upsert_funding_transfer(db, payload)
                if len(payloads) < size:
                    break
                current += 1

        mark_sync_completed(sync_state)
        db.commit()
        return inserted
    except Exception as exc:
        db.rollback()
        mark_sync_failed(db, "sync_funding_transfers", str(exc))
        db.commit()
        raise


def _upsert_p2p_order(db: Session, payload: dict) -> int:
    external_id = deterministic_external_id(
        "p2p_order",
        payload,
        ["orderNumber", "tradeType", "createTime"],
    )
    order_number = str(payload.get("orderNumber") or external_id)
    raw_event = upsert_raw_event(
        db,
        source="binance_c2c",
        event_type="P2P_ORDER",
        external_id=external_id,
        symbol=payload.get("asset"),
        event_time=parse_binance_time(payload.get("createTime")),
        payload=payload,
    )
    order = db.scalar(select(P2POrder).where(P2POrder.external_id == external_id))
    if order is None:
        order = P2POrder(external_id=external_id, order_number=order_number)
        db.add(order)
        inserted = 1
    else:
        inserted = 0

    order.raw_event_id = raw_event.id
    order.order_number = order_number
    order.trade_type = str(payload.get("tradeType") or "").upper()
    order.asset_code = str(payload.get("asset") or "").upper()
    order.fiat_code = _string_or_none(payload.get("fiat"))
    order.amount = _decimal(payload.get("amount"))
    order.total_price = _decimal(payload.get("totalPrice"))
    order.unit_price = _optional_decimal(payload.get("unitPrice"))
    order.commission = _decimal(payload.get("commission"))
    status = _string_or_none(payload.get("orderStatus"))
    order.order_status = None if status is None else status.upper()
    order.pay_method_name = _string_or_none(payload.get("payMethodName"))
    order.order_created_at = parse_binance_time(payload.get("createTime"))
    order.updated_at = utc_now()
    return inserted


def _upsert_funding_transfer(db: Session, payload: dict) -> int:
    external_id = deterministic_external_id(
        "funding_transfer",
        payload,
        ["tranId", "type", "timestamp"],
    )
    raw_event = upsert_raw_event(
        db,
        source="binance_wallet",
        event_type="FUNDING_TRANSFER",
        external_id=external_id,
        symbol=payload.get("asset"),
        event_time=parse_binance_time(payload.get("timestamp")),
        payload=payload,
    )
    transfer = db.scalar(
        select(FundingTransfer).where(FundingTransfer.external_id == external_id)
    )
    if transfer is None:
        transfer = FundingTransfer(
            external_id=external_id,
            tran_id=int(payload.get("tranId") or 0),
        )
        db.add(transfer)
        inserted = 1
    else:
        inserted = 0

    transfer.raw_event_id = raw_event.id
    transfer.tran_id = int(payload.get("tranId") or 0)
    transfer.transfer_type = str(payload.get("type") or "").upper()
    transfer.asset_code = str(payload.get("asset") or "").upper()
    transfer.amount = _decimal(payload.get("amount"))
    status = _string_or_none(payload.get("status"))
    transfer.status = None if status is None else status.upper()
    transfer.transferred_at = parse_binance_time(payload.get("timestamp"))
    transfer.updated_at = utc_now()
    return inserted


def _response_rows(response: dict | list[dict]) -> list[dict]:
    if isinstance(response, list):
        return response
    rows = response.get("data") or response.get("rows") or []
    if isinstance(rows, list):
        return rows
    if response.get("orderNumber") is not None:
        return [response]
    return []


def _decimal(value: object | None) -> Decimal:
    if value in (None, ""):
        return Decimal("0")
    return Decimal(str(value))


def _optional_decimal(value: object | None) -> Decimal | None:
    if value in (None, ""):
        return None
    return Decimal(str(value))


def _string_or_none(value: object | None) -> str | None:
    if value in (None, ""):
        return None
    return str(value)
