from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.accounting.ledger_builder import build_ledger_events, rebuild_lots
from app.binance.client import BinanceClient
from app.config import Settings
from app.db.models import EarnPosition, Lot, SpotBalance, TargetAllocation, utc_now
from app.ingestion.binance_records import mark_sync_completed, mark_sync_failed, mark_sync_started
from app.ingestion.sync_account import sync_account_info
from app.ingestion.sync_deposits import sync_deposits, sync_withdrawals
from app.ingestion.sync_earn import (
    sync_earn_positions,
    sync_earn_redemptions,
    sync_earn_rewards,
    sync_earn_subscriptions,
)
from app.ingestion.sync_prices import sync_exchange_info, sync_prices, sync_prices_for_assets
from app.ingestion.sync_trades import initial_trade_sync_requires_start_time, sync_spot_trades
from app.services.asset_utils import is_binance_earn_wrapper_asset
from app.services.portfolio_service import create_portfolio_snapshot

HISTORY_WINDOW = timedelta(days=29)


class SyncJobError(ValueError):
    pass


def run_sync_job(db: Session, settings: Settings, *, job_name: str) -> dict[str, Any]:
    job_name = job_name.strip()
    if job_name == "sync_account_info":
        return _with_client(settings, lambda client: sync_account_info(db, client), job_name)
    if job_name == "sync_exchange_info":
        return _with_client(
            settings,
            lambda client: sync_exchange_info(
                db,
                client,
                configured_symbols=settings.configured_symbols,
            ),
            job_name,
        )
    if job_name == "sync_prices":
        return _with_client(settings, lambda client: sync_prices(db, client), job_name)
    if job_name == "sync_tracked_asset_prices":
        return _with_client(
            settings,
            lambda client: sync_prices_for_assets(
                db,
                client,
                asset_codes=_tracked_asset_codes(db, base_asset=settings.portfolio_base_asset),
                base_asset=settings.portfolio_base_asset,
            ),
            job_name,
        )
    if job_name == "sync_spot_trades":
        return _trade_history_job(db, settings)
    if job_name == "sync_deposits":
        return _history_job(
            db,
            settings,
            job_name=job_name,
            run=lambda client, start_ms, end_ms: sync_deposits(
                db,
                client,
                start_time_ms=start_ms,
                end_time_ms=end_ms,
            ),
        )
    if job_name == "sync_withdrawals":
        return _history_job(
            db,
            settings,
            job_name=job_name,
            run=lambda client, start_ms, end_ms: sync_withdrawals(
                db,
                client,
                start_time_ms=start_ms,
                end_time_ms=end_ms,
            ),
        )
    if job_name == "sync_earn_positions":
        return _with_client(settings, lambda client: sync_earn_positions(db, client), job_name)
    if job_name == "sync_earn_subscriptions":
        return _history_job(
            db,
            settings,
            job_name=job_name,
            run=lambda client, start_ms, end_ms: sync_earn_subscriptions(
                db,
                client,
                start_time_ms=start_ms,
                end_time_ms=end_ms,
            ),
        )
    if job_name == "sync_earn_redemptions":
        return _history_job(
            db,
            settings,
            job_name=job_name,
            run=lambda client, start_ms, end_ms: sync_earn_redemptions(
                db,
                client,
                start_time_ms=start_ms,
                end_time_ms=end_ms,
            ),
        )
    if job_name == "sync_earn_rewards":
        return _history_job(
            db,
            settings,
            job_name=job_name,
            run=lambda client, start_ms, end_ms: sync_earn_rewards(
                db,
                client,
                start_time_ms=start_ms,
                end_time_ms=end_ms,
            ),
        )
    if job_name == "build_ledger":
        return _tracked_db_job(db, "build_ledger", lambda: build_ledger_events(db))
    if job_name == "rebuild_lots":
        return _tracked_db_job(db, "rebuild_lots", lambda: rebuild_lots(db))
    if job_name == "create_portfolio_snapshot":
        return _tracked_db_job(
            db,
            "create_portfolio_snapshot",
            lambda: create_portfolio_snapshot(
                db,
                base_asset=settings.portfolio_base_asset,
            ).id,
        )
    if job_name == "market_sync":
        return run_market_sync(db, settings)
    if job_name == "records_sync":
        return run_records_sync(db, settings)
    if job_name == "accounting_refresh":
        return run_accounting_refresh(db, settings)
    if job_name == "full_reconciliation":
        return run_full_reconciliation(db, settings)
    raise SyncJobError(f"Unknown sync job: {job_name}")


def run_market_sync(db: Session, settings: Settings) -> dict[str, Any]:
    results = {
        "sync_exchange_info": _run_grouped_job(db, settings, "sync_exchange_info"),
        "sync_prices": _run_grouped_job(db, settings, "sync_prices"),
        "sync_tracked_asset_prices": _run_grouped_job(
            db, settings, "sync_tracked_asset_prices"
        ),
    }
    return {"job_name": "market_sync", "results": results}


def run_records_sync(db: Session, settings: Settings) -> dict[str, Any]:
    job_names = [
        "sync_account_info",
        "sync_spot_trades",
        "sync_deposits",
        "sync_withdrawals",
        "sync_earn_positions",
        "sync_earn_subscriptions",
        "sync_earn_redemptions",
        "sync_earn_rewards",
    ]
    results = {}
    for job_name in job_names:
        results[job_name] = _run_grouped_job(db, settings, job_name)
    results["sync_tracked_asset_prices"] = _run_grouped_job(
        db,
        settings,
        "sync_tracked_asset_prices",
    )
    return {"job_name": "records_sync", "results": results}


def run_accounting_refresh(db: Session, settings: Settings) -> dict[str, Any]:
    results = {
        "build_ledger": _run_grouped_job(db, settings, "build_ledger"),
        "rebuild_lots": _run_grouped_job(db, settings, "rebuild_lots"),
        "create_portfolio_snapshot": _run_grouped_job(
            db, settings, "create_portfolio_snapshot"
        ),
    }
    return {"job_name": "accounting_refresh", "results": results}


def run_full_reconciliation(db: Session, settings: Settings) -> dict[str, Any]:
    results = {
        "market_sync": _run_grouped_callable(
            db,
            "market_sync",
            lambda: run_market_sync(db, settings),
        ),
        "records_sync": _run_grouped_callable(
            db,
            "records_sync",
            lambda: run_records_sync(db, settings),
        ),
        "accounting_refresh": _run_grouped_callable(
            db,
            "accounting_refresh",
            lambda: run_accounting_refresh(db, settings),
        ),
    }
    return {"job_name": "full_reconciliation", "results": results}


def _with_client(
    settings: Settings,
    run: Callable[[BinanceClient], int],
    job_name: str,
) -> dict[str, Any]:
    with BinanceClient.from_settings(settings) as client:
        count = run(client)
    return {"job_name": job_name, "count": count}


def _history_job(
    db: Session,
    settings: Settings,
    *,
    job_name: str,
    run: Callable[[BinanceClient, int, int], int],
) -> dict[str, Any]:
    if settings.binance_history_sync_start_ms is None:
        return _skipped_job(
            db,
            job_name,
            reason="BINANCE_HISTORY_SYNC_START_MS is not configured",
        )
    start_time_ms = settings.binance_history_sync_start_ms
    if start_time_ms is None:
        raise ValueError("BINANCE_HISTORY_SYNC_START_MS is required")

    with BinanceClient.from_settings(settings) as client:
        count = 0
        for window_start_ms, window_end_ms in _history_windows(start_time_ms):
            count += run(client, window_start_ms, window_end_ms)
    return {"job_name": job_name, "count": count}


def _trade_history_job(db: Session, settings: Settings) -> dict[str, Any]:
    if (
        settings.binance_trade_sync_start_ms is None
        and initial_trade_sync_requires_start_time(db, symbols=settings.configured_symbols)
    ):
        return _skipped_job(
            db,
            "sync_spot_trades",
            reason="BINANCE_TRADE_SYNC_START_MS is required before initial trade sync",
        )

    return _with_client(
        settings,
        lambda client: sync_spot_trades(
            db,
            client,
            start_time_ms=settings.binance_trade_sync_start_ms,
        ),
        "sync_spot_trades",
    )


def _skipped_job(db: Session, job_name: str, *, reason: str) -> dict[str, Any]:
    sync_state = mark_sync_started(db, job_name)
    sync_state.status = "skipped"
    sync_state.last_completed_at = utc_now()
    sync_state.error_message = reason
    db.commit()
    return {"job_name": job_name, "skipped": True, "reason": reason}


def _failed_job(db: Session, job_name: str, *, error: str) -> dict[str, Any]:
    sync_state = mark_sync_started(db, job_name)
    sync_state.status = "failed"
    sync_state.last_completed_at = utc_now()
    sync_state.error_message = error[:2000]
    db.commit()
    return {"job_name": job_name, "failed": True, "error": error}


def _run_grouped_job(db: Session, settings: Settings, job_name: str) -> dict[str, Any]:
    try:
        return run_sync_job(db, settings, job_name=job_name)
    except Exception as exc:
        db.rollback()
        return _failed_job(db, job_name, error=str(exc))


def _run_grouped_callable(db: Session, job_name: str, run: Callable[[], dict[str, Any]]) -> dict:
    try:
        return run()
    except Exception as exc:
        db.rollback()
        return _failed_job(db, job_name, error=str(exc))


def _history_windows(start_time_ms: int) -> list[tuple[int, int]]:
    start = datetime.fromtimestamp(start_time_ms / 1000, tz=UTC)
    now = datetime.now(UTC)
    if start >= now:
        current_ms = int(now.timestamp() * 1000)
        return [(start_time_ms, current_ms)]

    windows: list[tuple[int, int]] = []
    window_start = start
    while window_start < now:
        window_end = min(window_start + HISTORY_WINDOW, now)
        windows.append(
            (
                int(window_start.timestamp() * 1000),
                int(window_end.timestamp() * 1000),
            )
        )
        window_start = window_end + timedelta(milliseconds=1)
    return windows


def _tracked_asset_codes(db: Session, *, base_asset: str) -> list[str]:
    base_asset = base_asset.strip().upper()
    asset_codes: set[str] = set()
    for balance in db.scalars(select(SpotBalance)):
        if balance.total > 0 and not is_binance_earn_wrapper_asset(balance.asset_code):
            asset_codes.add(balance.asset_code)
    for position in db.scalars(select(EarnPosition).where(EarnPosition.amount > 0)):
        asset_codes.add(position.asset_code)
    for lot in db.scalars(select(Lot).where(Lot.remaining_quantity > 0)):
        asset_codes.add(lot.asset_code)
    for target in db.scalars(select(TargetAllocation).where(TargetAllocation.is_enabled.is_(True))):
        asset_codes.add(target.asset_code)
    asset_codes.discard(base_asset)
    return sorted(asset_codes)


def _tracked_db_job(db: Session, job_name: str, run: Callable[[], int]) -> dict[str, Any]:
    sync_state = mark_sync_started(db, job_name)
    try:
        count = run()
        mark_sync_completed(sync_state)
        db.commit()
        return {"job_name": job_name, "count": count}
    except Exception as exc:
        db.rollback()
        mark_sync_failed(db, job_name, str(exc))
        db.commit()
        raise
