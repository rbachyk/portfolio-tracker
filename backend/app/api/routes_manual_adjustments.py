from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.db.models import ManualAdjustment, utc_now
from app.db.session import get_db
from app.services.portfolio_service import decimal_to_string

router = APIRouter(prefix="/manual-adjustments", tags=["manual-adjustments"])


class ManualAdjustmentCreate(BaseModel):
    asset_code: str = Field(min_length=1, max_length=32)
    quantity: Decimal
    quote_asset_code: str | None = Field(default=None, max_length=32)
    quote_quantity: Decimal = Decimal("0")
    unit_price: Decimal | None = None
    reason: str | None = Field(default=None, max_length=2000)
    adjusted_at: datetime | None = None


@router.get("")
def manual_adjustments(db: Annotated[Session, Depends(get_db)]) -> dict:
    return {
        "manual_adjustments": [
            _manual_adjustment_to_dict(adjustment)
            for adjustment in db.scalars(
                select(ManualAdjustment).order_by(
                    desc(ManualAdjustment.adjusted_at),
                    desc(ManualAdjustment.id),
                )
            )
        ]
    }


@router.post("", status_code=status.HTTP_201_CREATED)
def create_manual_adjustment(
    payload: ManualAdjustmentCreate,
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    quantity = payload.quantity
    unit_price = payload.unit_price
    if unit_price is None and quantity != Decimal("0"):
        unit_price = abs(payload.quote_quantity / quantity)
    adjustment = ManualAdjustment(
        external_id=f"manual:{uuid4()}",
        asset_code=payload.asset_code.strip().upper(),
        symbol=None,
        quote_asset_code=None
        if payload.quote_asset_code is None
        else payload.quote_asset_code.strip().upper(),
        quantity=quantity,
        quote_quantity=payload.quote_quantity,
        unit_price=unit_price,
        reason=payload.reason,
        adjusted_at=payload.adjusted_at or utc_now(),
    )
    db.add(adjustment)
    db.commit()
    db.refresh(adjustment)
    return {"manual_adjustment": _manual_adjustment_to_dict(adjustment)}


def _manual_adjustment_to_dict(adjustment: ManualAdjustment) -> dict:
    return {
        "id": adjustment.id,
        "external_id": adjustment.external_id,
        "asset_code": adjustment.asset_code,
        "quantity": decimal_to_string(adjustment.quantity),
        "quote_asset_code": adjustment.quote_asset_code,
        "quote_quantity": decimal_to_string(adjustment.quote_quantity),
        "unit_price": None
        if adjustment.unit_price is None
        else decimal_to_string(adjustment.unit_price),
        "reason": adjustment.reason,
        "adjusted_at": adjustment.adjusted_at.isoformat(),
    }
