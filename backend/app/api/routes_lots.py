from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db.session import get_db
from app.services.dashboard_service import list_lots

router = APIRouter(prefix="/lots", tags=["lots"])


@router.get("")
def lots(
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    include_closed: Annotated[bool, Query()] = False,
) -> dict:
    return {
        "lots": list_lots(
            db,
            base_asset=settings.portfolio_base_asset,
            include_closed=include_closed,
        )
    }
