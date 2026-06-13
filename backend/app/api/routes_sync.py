from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings, get_settings
from app.db.models import SyncState
from app.db.session import get_db
from app.ingestion.binance_records import mark_sync_completed, mark_sync_failed, mark_sync_started
from app.services.dashboard_service import list_sync_states
from app.services.sync_service import is_sync_job_name, run_sync_job

router = APIRouter(prefix="/sync", tags=["sync"])


class SyncRunRequest(BaseModel):
    job_name: str = Field(min_length=1, max_length=128)


@router.get("/status")
def sync_status(db: Annotated[Session, Depends(get_db)]) -> dict:
    return {"jobs": list_sync_states(db)}


@router.post("/run", status_code=status.HTTP_202_ACCEPTED)
def run_sync(
    payload: SyncRunRequest,
    background_tasks: BackgroundTasks,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    job_name = payload.job_name.strip()
    if not is_sync_job_name(job_name):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown sync job: {job_name}",
        )

    sync_state = mark_sync_started(db, job_name)
    sync_state.progress_message = "Queued"
    db.commit()
    background_tasks.add_task(_run_sync_background, db.get_bind(), settings, job_name)
    return {"job_name": job_name, "status": "started"}


def _run_sync_background(bind, settings: Settings, job_name: str) -> None:
    session_factory = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=bind,
        expire_on_commit=False,
    )
    with session_factory() as db:
        try:
            sync_state = mark_sync_started(db, job_name)
            sync_state.progress_message = "Running"
            db.commit()
            run_sync_job(db, settings, job_name=job_name)
            sync_state = db.scalar(select(SyncState).where(SyncState.job_name == job_name))
            if sync_state is not None and sync_state.status == "running":
                mark_sync_completed(sync_state)
                db.commit()
        except Exception as exc:
            db.rollback()
            mark_sync_failed(db, job_name, str(exc))
            db.commit()
