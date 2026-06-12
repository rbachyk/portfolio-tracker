from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db.session import get_db, ping_database

router = APIRouter(tags=["health"])


@router.get("/health")
def health(settings: Annotated[Settings, Depends(get_settings)]) -> dict[str, str]:
    return {
        "status": "ok",
        "service": settings.app_name,
        "environment": settings.environment,
    }


@router.get("/health/db")
def database_health(db: Annotated[Session, Depends(get_db)]) -> dict[str, str]:
    ping_database(db)
    return {
        "status": "ok",
        "database": "ok",
    }
