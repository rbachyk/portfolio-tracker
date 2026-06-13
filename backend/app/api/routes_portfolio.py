from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db.session import get_db
from app.services.dashboard_service import get_overview, list_holdings
from app.services.portfolio_service import (
    MissingPriceError,
    create_portfolio_snapshot,
    drawdown_point_to_dict,
    equity_curve_point_to_dict,
    get_drawdown_curve,
    get_equity_curve,
    get_latest_portfolio_snapshot,
    list_portfolio_snapshots,
    portfolio_snapshot_to_dict,
)

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


@router.get("/overview")
def overview(
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    return get_overview(db, base_asset=settings.portfolio_base_asset)


@router.get("/holdings")
def holdings(
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    return {"holdings": list_holdings(db, base_asset=settings.portfolio_base_asset)}


@router.post("/snapshots", status_code=status.HTTP_201_CREATED)
def create_snapshot(
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    try:
        snapshot = create_portfolio_snapshot(
            db,
            base_asset=settings.portfolio_base_asset,
        )
    except MissingPriceError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "missing_prices", "assets": exc.missing_assets},
        ) from exc
    return portfolio_snapshot_to_dict(snapshot)


@router.get("/snapshots")
def snapshots(
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
) -> dict:
    return {
        "snapshots": [
            portfolio_snapshot_to_dict(snapshot)
            for snapshot in list_portfolio_snapshots(db, limit=limit)
        ]
    }


@router.get("/snapshots/latest")
def latest_snapshot(db: Annotated[Session, Depends(get_db)]) -> dict:
    snapshot = get_latest_portfolio_snapshot(db)
    if snapshot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No portfolio snapshots exist yet.",
        )
    return portfolio_snapshot_to_dict(snapshot)


@router.get("/performance/equity-curve")
def equity_curve(
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=5000)] = 365,
) -> dict:
    return {
        "points": [
            equity_curve_point_to_dict(point) for point in get_equity_curve(db, limit=limit)
        ]
    }


@router.get("/performance/drawdown")
def drawdown_curve(
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=5000)] = 365,
) -> dict:
    return {
        "points": [
            drawdown_point_to_dict(point) for point in get_drawdown_curve(db, limit=limit)
        ]
    }
