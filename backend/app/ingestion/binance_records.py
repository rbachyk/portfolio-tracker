from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import RawBinanceEvent, SyncState, utc_now


def deterministic_external_id(prefix: str, payload: dict, preferred_keys: list[str]) -> str:
    parts = [str(payload[key]) for key in preferred_keys if payload.get(key) not in (None, "")]
    if parts:
        return f"{prefix}:{':'.join(parts)}"

    canonical_payload = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    digest = hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest()
    return f"{prefix}:sha256:{digest}"


def upsert_raw_event(
    db: Session,
    *,
    source: str,
    event_type: str,
    external_id: str,
    payload: dict,
    symbol: str | None = None,
    event_time: datetime | None = None,
) -> RawBinanceEvent:
    raw_event = db.scalar(
        select(RawBinanceEvent).where(
            RawBinanceEvent.source == source,
            RawBinanceEvent.external_id == external_id,
        )
    )
    if raw_event is None:
        raw_event = RawBinanceEvent(
            source=source,
            event_type=event_type,
            external_id=external_id,
            symbol=symbol,
            event_time=event_time,
            payload=payload,
        )
        db.add(raw_event)
        db.flush()
    else:
        raw_event.event_type = event_type
        raw_event.symbol = symbol
        raw_event.event_time = event_time
        raw_event.payload = payload
        raw_event.updated_at = utc_now()

    return raw_event


def parse_binance_time(value: object | None) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, int | float):
        return datetime.fromtimestamp(int(value) / 1000, tz=UTC)
    if isinstance(value, str) and value.isdigit():
        return datetime.fromtimestamp(int(value) / 1000, tz=UTC)
    if isinstance(value, str):
        normalized_value = value.strip().replace("T", " ").replace("Z", "")
        try:
            return datetime.fromisoformat(normalized_value).replace(tzinfo=UTC)
        except ValueError:
            return datetime.strptime(normalized_value, "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC)
    raise TypeError(f"Unsupported Binance time value: {value!r}")


def mark_sync_started(db: Session, job_name: str) -> SyncState:
    now = utc_now()
    sync_state = db.scalar(select(SyncState).where(SyncState.job_name == job_name))
    if sync_state is None:
        sync_state = SyncState(job_name=job_name)
        db.add(sync_state)
    sync_state.status = "running"
    sync_state.last_started_at = now
    sync_state.error_message = None
    return sync_state


def mark_sync_completed(sync_state: SyncState) -> None:
    sync_state.status = "success"
    sync_state.last_completed_at = utc_now()
    sync_state.error_message = None


def mark_sync_failed(db: Session, job_name: str, error_message: str) -> None:
    sync_state = db.scalar(select(SyncState).where(SyncState.job_name == job_name))
    if sync_state is None:
        sync_state = SyncState(job_name=job_name)
        db.add(sync_state)
    sync_state.status = "failed"
    sync_state.error_message = error_message[:2000]
