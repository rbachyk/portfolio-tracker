from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import structlog

from app.config import get_settings
from app.db.session import SessionLocal
from app.logging import configure_logging
from app.services.sync_service import (
    run_accounting_refresh,
    run_full_reconciliation,
    run_market_sync,
    run_records_sync,
)

settings = get_settings()
configure_logging(settings.log_level)
logger = structlog.get_logger(__name__)


@dataclass
class ScheduledJob:
    name: str
    interval: timedelta
    run: Callable
    next_run_at: datetime


def main() -> None:
    logger.info("worker.startup")
    jobs = [
        ScheduledJob(
            name="market_sync",
            interval=timedelta(seconds=settings.price_sync_interval_seconds),
            run=run_market_sync,
            next_run_at=datetime.now(UTC),
        ),
        ScheduledJob(
            name="records_sync",
            interval=timedelta(seconds=settings.records_sync_interval_seconds),
            run=run_records_sync,
            next_run_at=datetime.now(UTC) + timedelta(seconds=15),
        ),
        ScheduledJob(
            name="accounting_refresh",
            interval=timedelta(seconds=settings.snapshot_interval_seconds),
            run=run_accounting_refresh,
            next_run_at=datetime.now(UTC) + timedelta(seconds=30),
        ),
        ScheduledJob(
            name="full_reconciliation",
            interval=timedelta(seconds=settings.full_reconciliation_interval_seconds),
            run=run_full_reconciliation,
            next_run_at=datetime.now(UTC) + timedelta(seconds=60),
        ),
    ]

    while True:
        now = datetime.now(UTC)
        for job in jobs:
            if job.next_run_at > now:
                continue
            _run_job(job)
            job.next_run_at = datetime.now(UTC) + job.interval
        time.sleep(settings.worker_poll_interval_seconds)


def _run_job(job: ScheduledJob) -> None:
    logger.info("worker.job.started", job_name=job.name)
    with SessionLocal() as db:
        try:
            job.run(db, settings)
        except Exception as exc:
            logger.exception("worker.job.failed", job_name=job.name, error=str(exc))
        else:
            logger.info("worker.job.completed", job_name=job.name)


if __name__ == "__main__":
    main()
