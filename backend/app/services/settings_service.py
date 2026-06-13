from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.db.models import Setting, TargetAllocation, utc_now


def get_effective_settings(db: Session, settings: Settings) -> dict[str, Any]:
    persisted = {row.key: row.value for row in db.scalars(select(Setting))}
    return {
        "portfolio_base_asset": persisted.get(
            "portfolio_base_asset", settings.portfolio_base_asset
        ),
        "cost_basis_method": persisted.get("cost_basis_method", settings.cost_basis_method),
        "include_earn_rewards_in_pnl": persisted.get(
            "include_earn_rewards_in_pnl",
            settings.include_earn_rewards_in_pnl,
        ),
        "price_sync_interval_seconds": persisted.get(
            "price_sync_interval_seconds",
            settings.price_sync_interval_seconds,
        ),
        "records_sync_interval_seconds": persisted.get(
            "records_sync_interval_seconds",
            settings.records_sync_interval_seconds,
        ),
        "snapshot_interval_seconds": persisted.get(
            "snapshot_interval_seconds",
            settings.snapshot_interval_seconds,
        ),
        "full_reconciliation_interval_seconds": persisted.get(
            "full_reconciliation_interval_seconds",
            settings.full_reconciliation_interval_seconds,
        ),
    }


def update_settings(db: Session, values: dict[str, Any]) -> dict[str, Any]:
    for key, value in values.items():
        setting = db.scalar(select(Setting).where(Setting.key == key))
        if setting is None:
            setting = Setting(key=key, value=value)
            db.add(setting)
        else:
            setting.value = value
            setting.updated_at = utc_now()
    db.commit()
    return {row.key: row.value for row in db.scalars(select(Setting))}


def list_target_allocations(db: Session) -> list[dict]:
    return [
        _target_to_dict(target)
        for target in db.scalars(select(TargetAllocation).order_by(TargetAllocation.asset_code))
    ]


def upsert_target_allocation(
    db: Session,
    *,
    asset_code: str,
    target_pct: Decimal,
    is_enabled: bool = True,
) -> dict:
    normalized_asset = asset_code.strip().upper()
    target = db.scalar(
        select(TargetAllocation).where(TargetAllocation.asset_code == normalized_asset)
    )
    if target is None:
        target = TargetAllocation(asset_code=normalized_asset)
        db.add(target)
    target.target_pct = target_pct
    target.is_enabled = is_enabled
    target.updated_at = utc_now()
    db.commit()
    db.refresh(target)
    return _target_to_dict(target)


def delete_target_allocation(db: Session, *, asset_code: str) -> bool:
    target = db.scalar(
        select(TargetAllocation).where(TargetAllocation.asset_code == asset_code.strip().upper())
    )
    if target is None:
        return False
    db.delete(target)
    db.commit()
    return True


def _target_to_dict(target: TargetAllocation) -> dict:
    return {
        "asset_code": target.asset_code,
        "target_pct": str(target.target_pct.normalize()),
        "is_enabled": target.is_enabled,
    }
