from __future__ import annotations

from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db.session import get_db
from app.services.settings_service import (
    delete_target_allocation,
    get_effective_settings,
    list_target_allocations,
    update_settings,
    upsert_target_allocation,
)

router = APIRouter(prefix="/settings", tags=["settings"])


class SettingsUpdate(BaseModel):
    portfolio_base_asset: str | None = Field(default=None, min_length=1, max_length=32)
    cost_basis_method: str | None = Field(default=None, pattern="^(FIFO|LIFO|HIFO|AVERAGE)$")
    include_earn_rewards_in_pnl: bool | None = None
    price_sync_interval_seconds: int | None = Field(default=None, ge=60)
    records_sync_interval_seconds: int | None = Field(default=None, ge=300)
    snapshot_interval_seconds: int | None = Field(default=None, ge=300)
    full_reconciliation_interval_seconds: int | None = Field(default=None, ge=3600)


class TargetAllocationUpdate(BaseModel):
    asset_code: str = Field(min_length=1, max_length=32)
    target_pct: Decimal = Field(ge=Decimal("0"), le=Decimal("1"))
    is_enabled: bool = True


@router.get("")
def settings(
    db: Annotated[Session, Depends(get_db)],
    app_settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    return {
        "settings": get_effective_settings(db, app_settings),
        "target_allocations": list_target_allocations(db),
        "binance_api_configured": bool(
            app_settings.binance_api_key_value and app_settings.binance_api_secret_value
        ),
    }


@router.patch("")
def patch_settings(
    payload: SettingsUpdate,
    db: Annotated[Session, Depends(get_db)],
    app_settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    values = payload.model_dump(exclude_none=True)
    if "portfolio_base_asset" in values:
        values["portfolio_base_asset"] = values["portfolio_base_asset"].strip().upper()
    update_settings(db, values)
    return {"settings": get_effective_settings(db, app_settings)}


@router.post("/target-allocations", status_code=status.HTTP_201_CREATED)
def save_target_allocation(
    payload: TargetAllocationUpdate,
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    return {
        "target_allocation": upsert_target_allocation(
            db,
            asset_code=payload.asset_code,
            target_pct=payload.target_pct,
            is_enabled=payload.is_enabled,
        )
    }


@router.delete("/target-allocations/{asset_code}")
def remove_target_allocation(asset_code: str, db: Annotated[Session, Depends(get_db)]) -> dict:
    if not delete_target_allocation(db, asset_code=asset_code):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target allocation not found",
        )
    return {"status": "ok"}
