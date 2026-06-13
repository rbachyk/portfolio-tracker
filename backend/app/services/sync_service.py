from __future__ import annotations

from collections.abc import Callable
from typing import Any

from sqlalchemy.orm import Session

from app.accounting.ledger_builder import build_ledger_events, rebuild_lots
from app.binance.client import BinanceClient
from app.config import Settings
from app.ingestion.binance_records import mark_sync_completed, mark_sync_failed, mark_sync_started
from app.ingestion.sync_account import sync_account_info
from app.ingestion.sync_deposits import sync_deposits, sync_withdrawals
from app.ingestion.sync_earn import (
    sync_earn_positions,
    sync_earn_redemptions,
    sync_earn_rewards,
    sync_earn_subscriptions,
)
from app.ingestion.sync_prices import sync_exchange_info, sync_prices
from app.ingestion.sync_trades import sync_spot_trades
from app.services.portfolio_service import create_portfolio_snapshot


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
    if job_name == "sync_spot_trades":
        return _with_client(
            settings,
            lambda client: sync_spot_trades(
                db,
                client,
                start_time_ms=settings.binance_trade_sync_start_ms,
            ),
            job_name,
        )
    if job_name == "sync_deposits":
        return _history_job(
            db,
            settings,
            job_name=job_name,
            run=lambda client, start_ms: sync_deposits(db, client, start_time_ms=start_ms),
        )
    if job_name == "sync_withdrawals":
        return _history_job(
            db,
            settings,
            job_name=job_name,
            run=lambda client, start_ms: sync_withdrawals(db, client, start_time_ms=start_ms),
        )
    if job_name == "sync_earn_positions":
        return _with_client(settings, lambda client: sync_earn_positions(db, client), job_name)
    if job_name == "sync_earn_subscriptions":
        return _history_job(
            db,
            settings,
            job_name=job_name,
            run=lambda client, start_ms: sync_earn_subscriptions(
                db,
                client,
                start_time_ms=start_ms,
            ),
        )
    if job_name == "sync_earn_redemptions":
        return _history_job(
            db,
            settings,
            job_name=job_name,
            run=lambda client, start_ms: sync_earn_redemptions(
                db,
                client,
                start_time_ms=start_ms,
            ),
        )
    if job_name == "sync_earn_rewards":
        return _history_job(
            db,
            settings,
            job_name=job_name,
            run=lambda client, start_ms: sync_earn_rewards(
                db,
                client,
                start_time_ms=start_ms,
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
        "sync_exchange_info": run_sync_job(db, settings, job_name="sync_exchange_info"),
        "sync_prices": run_sync_job(db, settings, job_name="sync_prices"),
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
        results[job_name] = run_sync_job(db, settings, job_name=job_name)
    return {"job_name": "records_sync", "results": results}


def run_accounting_refresh(db: Session, settings: Settings) -> dict[str, Any]:
    results = {
        "build_ledger": run_sync_job(db, settings, job_name="build_ledger"),
        "rebuild_lots": run_sync_job(db, settings, job_name="rebuild_lots"),
        "create_portfolio_snapshot": run_sync_job(
            db,
            settings,
            job_name="create_portfolio_snapshot",
        ),
    }
    return {"job_name": "accounting_refresh", "results": results}


def run_full_reconciliation(db: Session, settings: Settings) -> dict[str, Any]:
    results = {
        "market_sync": run_market_sync(db, settings),
        "records_sync": run_records_sync(db, settings),
        "accounting_refresh": run_accounting_refresh(db, settings),
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
    run: Callable[[BinanceClient, int], int],
) -> dict[str, Any]:
    if settings.binance_history_sync_start_ms is None:
        return {
            "job_name": job_name,
            "skipped": True,
            "reason": "BINANCE_HISTORY_SYNC_START_MS is not configured",
        }
    return _with_client(
        settings,
        lambda client: run(client, settings.binance_history_sync_start_ms or 0),
        job_name,
    )


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
