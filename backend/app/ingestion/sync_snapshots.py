from __future__ import annotations

from sqlalchemy.orm import Session

from app.services.portfolio_service import create_portfolio_snapshot


def sync_portfolio_snapshot(db: Session, *, base_asset: str) -> int:
    create_portfolio_snapshot(db, base_asset=base_asset)
    return 1
