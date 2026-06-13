from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.dashboard_service import get_cash_flows

router = APIRouter(prefix="/deposits", tags=["deposits"])


@router.get("")
def deposits(db: Annotated[Session, Depends(get_db)]) -> dict:
    return get_cash_flows(db)
