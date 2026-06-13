from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db.session import get_db
from app.services.dashboard_service import get_earn_dashboard

router = APIRouter(prefix="/earn", tags=["earn"])


@router.get("")
def earn(
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    return get_earn_dashboard(db, base_asset=settings.portfolio_base_asset)
