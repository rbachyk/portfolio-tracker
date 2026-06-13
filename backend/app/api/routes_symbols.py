from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.dashboard_service import list_symbols

router = APIRouter(prefix="/symbols", tags=["symbols"])


@router.get("")
def symbols(db: Annotated[Session, Depends(get_db)]) -> dict:
    return {"symbols": list_symbols(db)}
