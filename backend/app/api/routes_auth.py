from __future__ import annotations

from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.dependencies import require_current_user
from app.config import Settings, get_settings
from app.db.models import User
from app.db.session import get_db
from app.services.auth_service import (
    AuthenticationError,
    authenticate_user,
    change_password,
    create_access_token,
)

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=512)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=512)
    new_password: str = Field(min_length=12, max_length=512)


@router.post("/login")
def login(
    payload: LoginRequest,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    try:
        user = authenticate_user(
            db,
            settings,
            username=payload.username,
            password=payload.password,
        )
    except AuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        ) from exc

    token, expires_at = create_access_token(
        subject=user.username,
        secret=settings.session_secret_value,
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_at": expires_at.isoformat(),
        "username": user.username,
    }


@router.get("/me")
def me(user: Annotated[User, Depends(require_current_user)]) -> dict:
    return {
        "username": user.username,
        "last_login_at": None if user.last_login_at is None else user.last_login_at.isoformat(),
    }


@router.post("/change-password")
def update_password(
    payload: ChangePasswordRequest,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    user: Annotated[User, Depends(require_current_user)],
) -> dict:
    try:
        authenticate_user(
            db,
            settings,
            username=user.username,
            password=payload.current_password,
        )
    except AuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        ) from exc

    change_password(db, user, new_password=payload.new_password)
    return {"status": "ok"}
