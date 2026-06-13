from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.db.models import User, utc_now


class AuthenticationError(ValueError):
    pass


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def authenticate_user(
    db: Session,
    settings: Settings,
    *,
    username: str,
    password: str,
) -> User:
    normalized_username = username.strip()
    user = db.scalar(select(User).where(User.username == normalized_username))

    if user is None:
        env_hash = settings.dashboard_password_hash_value
        if normalized_username != settings.dashboard_username or env_hash is None:
            raise AuthenticationError("Invalid username or password")
        if not verify_password(password, env_hash):
            raise AuthenticationError("Invalid username or password")
        user = User(username=normalized_username, password_hash=env_hash)
        db.add(user)
        db.flush()
    elif not user.is_active or not verify_password(password, user.password_hash):
        raise AuthenticationError("Invalid username or password")

    user.last_login_at = utc_now()
    db.commit()
    db.refresh(user)
    return user


def change_password(db: Session, user: User, *, new_password: str) -> User:
    user.password_hash = hash_password(new_password)
    user.updated_at = utc_now()
    db.commit()
    db.refresh(user)
    return user


def create_access_token(
    *,
    subject: str,
    secret: str,
    expires_delta: timedelta,
) -> tuple[str, datetime]:
    now = datetime.now(UTC)
    expires_at = now + expires_delta
    payload = {
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
        "nonce": secrets.token_urlsafe(16),
    }
    encoded_payload = _b64encode_json(payload)
    signature = _sign(encoded_payload, secret)
    return f"{encoded_payload}.{signature}", expires_at


def decode_access_token(token: str, *, secret: str) -> dict[str, Any]:
    try:
        encoded_payload, signature = token.split(".", 1)
    except ValueError as exc:
        raise AuthenticationError("Invalid access token") from exc

    expected_signature = _sign(encoded_payload, secret)
    if not hmac.compare_digest(signature, expected_signature):
        raise AuthenticationError("Invalid access token")

    payload = _b64decode_json(encoded_payload)
    expires_at = int(payload.get("exp", 0))
    if expires_at < int(datetime.now(UTC).timestamp()):
        raise AuthenticationError("Access token expired")
    if not payload.get("sub"):
        raise AuthenticationError("Invalid access token")
    return payload


def _sign(encoded_payload: str, secret: str) -> str:
    digest = hmac.new(
        secret.encode("utf-8"),
        encoded_payload.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return _b64encode_bytes(digest)


def _b64encode_json(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return _b64encode_bytes(raw)


def _b64decode_json(value: str) -> dict[str, Any]:
    padded = value + ("=" * (-len(value) % 4))
    return json.loads(base64.urlsafe_b64decode(padded.encode("ascii")))


def _b64encode_bytes(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")
