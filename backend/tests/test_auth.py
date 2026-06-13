from collections.abc import Generator

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import Settings, get_settings
from app.db.models import Base, User
from app.db.session import get_db
from app.main import app
from app.services.auth_service import hash_password


def make_session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_login_uses_bcrypt_hash_and_returns_authenticated_user() -> None:
    db = make_session()
    settings = Settings(
        dashboard_username="admin",
        dashboard_password_hash=hash_password("correct horse battery staple"),
        session_secret="test-session-secret",
    )

    def override_get_db() -> Generator[Session, None, None]:
        yield db

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_settings] = lambda: settings

    try:
        client = TestClient(app)
        login_response = client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "correct horse battery staple"},
        )
        token = login_response.json()["access_token"]
        me_response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    finally:
        app.dependency_overrides.clear()

    assert login_response.status_code == 200
    assert login_response.json()["token_type"] == "bearer"
    assert me_response.status_code == 200
    assert me_response.json()["username"] == "admin"
    assert db.query(User).filter_by(username="admin").one().password_hash.startswith("$2")


def test_login_rejects_invalid_password() -> None:
    db = make_session()
    settings = Settings(
        dashboard_username="admin",
        dashboard_password_hash=hash_password("correct horse battery staple"),
        session_secret="test-session-secret",
    )

    def override_get_db() -> Generator[Session, None, None]:
        yield db

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_settings] = lambda: settings

    try:
        client = TestClient(app)
        response = client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "wrong password"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 401
