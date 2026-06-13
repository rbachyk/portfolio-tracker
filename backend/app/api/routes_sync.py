from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db.session import get_db
from app.services.dashboard_service import list_sync_states
from app.services.sync_service import SyncJobError, run_sync_job

router = APIRouter(prefix="/sync", tags=["sync"])


class SyncRunRequest(BaseModel):
    job_name: str = Field(min_length=1, max_length=128)


@router.get("/status")
def sync_status(db: Annotated[Session, Depends(get_db)]) -> dict:
    return {"jobs": list_sync_states(db)}


@router.post("/run")
def run_sync(
    payload: SyncRunRequest,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    try:
        return run_sync_job(db, settings, job_name=payload.job_name)
    except SyncJobError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
