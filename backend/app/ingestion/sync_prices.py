from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.binance.client import BinanceClient
from app.db.models import Asset, PriceSnapshot, Symbol, SyncState, utc_now


def sync_exchange_info(
    db: Session,
    client: BinanceClient,
    *,
    configured_symbols: Sequence[str] | None,
) -> int:
    normalized_configured = _normalize_symbols(configured_symbols)
    if configured_symbols is not None:
        _disable_symbols_not_configured(db, normalized_configured)
        if not normalized_configured:
            db.commit()
            return 0

    response = client.get_exchange_info(normalized_configured or None)
    symbols = response.get("symbols", [])

    synced = 0
    for payload in symbols:
        symbol_name = payload["symbol"].upper()
        _upsert_asset(db, payload.get("baseAsset"))
        _upsert_asset(db, payload.get("quoteAsset"))
        symbol = _get_symbol(db, symbol_name)

        if symbol is None:
            symbol = Symbol(symbol=symbol_name)
            db.add(symbol)

        symbol.base_asset_code = payload.get("baseAsset")
        symbol.quote_asset_code = payload.get("quoteAsset")
        symbol.status = payload.get("status")
        symbol.is_spot_trading_allowed = bool(payload.get("isSpotTradingAllowed", False))
        if normalized_configured:
            symbol.is_enabled = symbol_name in normalized_configured
        symbol.raw_payload = payload
        synced += 1

    db.commit()
    return synced


def sync_prices(
    db: Session,
    client: BinanceClient,
    *,
    symbols: Sequence[str] | None = None,
) -> int:
    sync_state = _mark_sync_started(db, "sync_prices")
    try:
        target_symbols = _normalize_symbols(symbols) or _enabled_symbols(db)
        if not target_symbols:
            _mark_sync_completed(db, sync_state)
            db.commit()
            return 0

        response = client.get_ticker_prices(target_symbols)
        tickers = [response] if isinstance(response, dict) else response
        observed_at = utc_now()

        inserted = 0
        for ticker in tickers:
            symbol_name = ticker["symbol"].upper()
            symbol = _get_symbol(db, symbol_name)
            if symbol is None:
                continue

            db.add(
                PriceSnapshot(
                    symbol_id=symbol.id,
                    symbol=symbol_name,
                    price=Decimal(ticker["price"]),
                    observed_at=observed_at,
                    raw_payload=ticker,
                )
            )
            inserted += 1

        _mark_sync_completed(db, sync_state)
        db.commit()
        return inserted
    except Exception as exc:
        db.rollback()
        _mark_sync_failed(db, "sync_prices", str(exc))
        db.commit()
        raise


def _normalize_symbols(symbols: Sequence[str] | None) -> set[str]:
    return {symbol.strip().upper() for symbol in symbols or [] if symbol.strip()}


def _enabled_symbols(db: Session) -> set[str]:
    return set(db.scalars(select(Symbol.symbol).where(Symbol.is_enabled.is_(True))).all())


def _disable_symbols_not_configured(db: Session, configured_symbols: set[str]) -> None:
    for symbol in db.scalars(select(Symbol).where(Symbol.is_enabled.is_(True))).all():
        if symbol.symbol not in configured_symbols:
            symbol.is_enabled = False


def _upsert_asset(db: Session, asset_code: str | None) -> Asset | None:
    if asset_code is None:
        return None

    asset_code = asset_code.upper()
    asset = db.scalar(select(Asset).where(Asset.code == asset_code))
    if asset is None:
        asset = Asset(code=asset_code)
        db.add(asset)
    return asset


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
    return sync_state


def _mark_sync_completed(db: Session, sync_state: SyncState) -> None:
    sync_state.status = "success"
    sync_state.last_completed_at = utc_now()
    sync_state.error_message = None


def _mark_sync_failed(db: Session, job_name: str, error_message: str) -> None:
    sync_state = db.scalar(select(SyncState).where(SyncState.job_name == job_name))
    if sync_state is None:
        sync_state = SyncState(job_name=job_name)
        db.add(sync_state)
    sync_state.status = "failed"
    sync_state.error_message = error_message[:2000]
