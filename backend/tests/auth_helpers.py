from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.deps_auth import get_db_session
from app.core.config import get_settings
from app.db.base import Base
from app.db.session import get_engine
from app.main import app


def setup_test_db(tmp_path, monkeypatch):
    db_path = tmp_path / "app-test.sqlite3"
    monkeypatch.setenv("ASYA_DB_PATH", db_path.as_posix())
    monkeypatch.setenv("AUTH_REGISTRATION_MODE", "open")
    monkeypatch.setenv("AUTH_SESSION_HASH_SECRET", "test-secret")
    monkeypatch.setenv("AUTH_COOKIE_NAME", "asya_session")
    get_settings.cache_clear()
    get_engine.cache_clear()
    settings = get_settings()
    engine = get_engine(settings.asya_db_url)
    Base.metadata.create_all(engine)
    return settings, engine


def override_db_session(engine):
    def _override():
        session = Session(bind=engine)
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    return _override


def build_authed_client(tmp_path, monkeypatch, email: str, display_name: str = "User") -> TestClient:
    settings, engine = setup_test_db(tmp_path, monkeypatch)
    app.dependency_overrides[get_db_session] = override_db_session(engine)
    client = TestClient(app)
    client.post(
        "/api/auth/register",
        json={"email": email, "display_name": display_name, "password": "strong-pass-123"},
    )
    login = client.post("/api/auth/login", json={"email": email, "password": "strong-pass-123"})
    assert login.status_code == 200
    return client
