from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.binance.client import BinanceClient
from app.db.models import RawBinanceEvent, Symbol, SyncState, Trade, utc_now

DEFAULT_TRADE_LIMIT = 1000


def sync_spot_trades(
    db: Session,
    client: BinanceClient,
    *,
    symbols: Sequence[str] | None = None,
    start_time_ms: int | None = None,
    limit: int = DEFAULT_TRADE_LIMIT,
) -> int:
    sync_state = _mark_sync_started(db, "sync_spot_trades")
    try:
        target_symbols = sorted(_normalize_symbols(symbols) or _enabled_symbols(db))
        sync_state.progress_current = 0
        sync_state.progress_total = len(target_symbols)
        db.commit()
        inserted = 0

        for index, symbol_name in enumerate(target_symbols, start=1):
            symbol = _get_symbol(db, symbol_name)
            if symbol is None:
                sync_state.progress_current = index
                db.commit()
                continue

            inserted += _sync_symbol_trades(
                db,
                client,
                symbol=symbol,
                start_time_ms=start_time_ms,
                limit=limit,
            )
            sync_state.progress_current = index
            db.commit()

        _mark_sync_completed(db, sync_state)
        db.commit()
        return inserted
    except Exception as exc:
        db.rollback()
        _mark_sync_failed(db, "sync_spot_trades", str(exc))
        db.commit()
        raise


def initial_trade_sync_requires_start_time(
    db: Session,
    *,
    symbols: Sequence[str] | None = None,
) -> bool:
    target_symbols = _normalize_symbols(symbols) or _enabled_symbols(db)
    for symbol_name in sorted(target_symbols):
        symbol = _get_symbol(db, symbol_name)
        if symbol is not None and _next_trade_from_id(db, symbol.symbol) is None:
            return True
    return False


def _sync_symbol_trades(
    db: Session,
    client: BinanceClient,
    *,
    symbol: Symbol,
    start_time_ms: int | None,
    limit: int,
) -> int:
    from_id = _next_trade_from_id(db, symbol.symbol)
    if from_id is None and start_time_ms is None:
        raise ValueError(
            f"Initial trade sync for {symbol.symbol} requires BINANCE_TRADE_SYNC_START_MS"
        )

    first_request = True
    inserted = 0

    while True:
        trades = client.get_my_trades(
            symbol=symbol.symbol,
            from_id=from_id,
            start_time_ms=start_time_ms if from_id is None and first_request else None,
            limit=limit,
        )
        if not trades:
            return inserted

        for payload in trades:
            inserted += _upsert_trade(db, symbol, payload)

        max_trade_id = max(int(payload["id"]) for payload in trades)
        from_id = max_trade_id + 1
        first_request = False

        if len(trades) < limit:
            return inserted


def _upsert_trade(db: Session, symbol: Symbol, payload: dict) -> int:
    trade_id = int(payload["id"])
    raw_event = _upsert_raw_trade_event(db, symbol.symbol, payload)

    existing_trade = db.scalar(
        select(Trade).where(
            Trade.symbol == symbol.symbol,
            Trade.binance_trade_id == trade_id,
        )
    )

    if existing_trade is not None:
        existing_trade.raw_event_id = raw_event.id
        existing_trade.updated_at = utc_now()
        return 0

    is_buyer = bool(payload["isBuyer"])
    db.add(
        Trade(
            symbol_id=symbol.id,
            raw_event_id=raw_event.id,
            symbol=symbol.symbol,
            base_asset_code=symbol.base_asset_code or "",
            quote_asset_code=symbol.quote_asset_code or "",
            side="BUY" if is_buyer else "SELL",
            binance_trade_id=trade_id,
            binance_order_id=int(payload["orderId"]),
            binance_order_list_id=_optional_int(payload.get("orderListId")),
            price=Decimal(payload["price"]),
            quantity=Decimal(payload["qty"]),
            quote_quantity=Decimal(payload["quoteQty"]),
            fee_asset_code=payload.get("commissionAsset"),
            fee_amount=Decimal(payload["commission"]),
            executed_at=_datetime_from_ms(int(payload["time"])),
            is_buyer=is_buyer,
            is_maker=bool(payload["isMaker"]),
            is_best_match=payload.get("isBestMatch"),
        )
    )
    return 1


def _upsert_raw_trade_event(db: Session, symbol: str, payload: dict) -> RawBinanceEvent:
    external_id = _raw_trade_external_id(symbol, int(payload["id"]))
    raw_event = db.scalar(
        select(RawBinanceEvent).where(
            RawBinanceEvent.source == "binance_spot",
            RawBinanceEvent.external_id == external_id,
        )
    )
    event_time = _datetime_from_ms(int(payload["time"]))

    if raw_event is None:
        raw_event = RawBinanceEvent(
            source="binance_spot",
            event_type="SPOT_TRADE",
            external_id=external_id,
            symbol=symbol,
            event_time=event_time,
            payload=payload,
        )
        db.add(raw_event)
        db.flush()
    else:
        raw_event.event_time = event_time
        raw_event.payload = payload
        raw_event.updated_at = utc_now()

    return raw_event


def _raw_trade_external_id(symbol: str, trade_id: int) -> str:
    return f"spot_trade:{symbol.upper()}:{trade_id}"


def _next_trade_from_id(db: Session, symbol: str) -> int | None:
    max_trade_id = db.scalar(select(func.max(Trade.binance_trade_id)).where(Trade.symbol == symbol))
    if max_trade_id is None:
        return None
    return int(max_trade_id) + 1


def _datetime_from_ms(timestamp_ms: int) -> datetime:
    return datetime.fromtimestamp(timestamp_ms / 1000, tz=UTC)


def _optional_int(value: object | None) -> int | None:
    if value is None:
        return None
    return int(value)


def _normalize_symbols(symbols: Sequence[str] | None) -> set[str]:
    return {symbol.strip().upper() for symbol in symbols or [] if symbol.strip()}


def _enabled_symbols(db: Session) -> set[str]:
    return set(db.scalars(select(Symbol.symbol).where(Symbol.is_enabled.is_(True))).all())


def _get_symbol(db: Session, symbol: str) -> Symbol | None:
    return db.scalar(select(Symbol).where(Symbol.symbol == symbol))


def _mark_sync_started(db: Session, job_name: str) -> SyncState:
    now = utc_now()
    sync_state = db.scalar(select(SyncState).where(SyncState.job_name == job_name))
    if sync_state is None:
        sync_state = SyncState(job_name=job_name)
        db.add(sync_state)
    sync_state.status = "running"
    sync_state.last_started_at = now
    sync_state.error_message = None
    sync_state.progress_current = 0
    sync_state.progress_total = None
    sync_state.progress_message = None
    return sync_state


def _mark_sync_completed(db: Session, sync_state: SyncState) -> None:
    sync_state.status = "success"
    sync_state.last_completed_at = utc_now()
    sync_state.error_message = None
    if sync_state.progress_total is not None:
        sync_state.progress_current = sync_state.progress_total


def _mark_sync_failed(db: Session, job_name: str, error_message: str) -> None:
    sync_state = db.scalar(select(SyncState).where(SyncState.job_name == job_name))
    if sync_state is None:
        sync_state = SyncState(job_name=job_name)
        db.add(sync_state)
    sync_state.status = "failed"
    sync_state.error_message = error_message[:2000]
