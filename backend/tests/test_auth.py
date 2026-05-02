from app.api.deps_auth import get_db_session
from app.core.config import get_settings
from app.db.base import Base
from app.db.session import get_engine
from app.main import app
from app.services.auth_service import AuthService
from app.services.user_service import UserService
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models.common import UserStatus


def _setup_test_db(tmp_path, monkeypatch):
    db_path = tmp_path / "auth.sqlite3"
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


def _override_db_session(engine):
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


def test_auth_register_login_me_logout_flow(tmp_path, monkeypatch) -> None:
    settings, engine = _setup_test_db(tmp_path, monkeypatch)
    app.dependency_overrides[get_db_session] = _override_db_session(engine)
    client = TestClient(app)

    register = client.post(
        "/api/auth/register",
        json={"email": "user@example.com", "display_name": "User", "password": "strong-pass-123"},
    )
    assert register.status_code == 200
    assert register.json()["status"] == "registered"
    assert register.json()["user"]["email"] == "user@example.com"

    login = client.post("/api/auth/login", json={"email": "user@example.com", "password": "strong-pass-123"})
    assert login.status_code == 200
    assert login.cookies.get(settings.auth_cookie_name)
    assert isinstance(login.json().get("preferred_chat_id"), str)

    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == "user@example.com"
    assert isinstance(me.json().get("preferred_chat_id"), str)

    logout = client.post("/api/auth/logout")
    assert logout.status_code == 200

    me_after = client.get("/api/auth/me")
    assert me_after.status_code == 401
    app.dependency_overrides.clear()


def test_auth_wrong_password_rejected(tmp_path, monkeypatch) -> None:
    _, engine = _setup_test_db(tmp_path, monkeypatch)
    app.dependency_overrides[get_db_session] = _override_db_session(engine)
    client = TestClient(app)
    client.post(
        "/api/auth/register",
        json={"email": "user@example.com", "display_name": "User", "password": "strong-pass-123"},
    )

    bad_login = client.post("/api/auth/login", json={"email": "user@example.com", "password": "wrong-pass-123"})
    assert bad_login.status_code == 401
    app.dependency_overrides.clear()


def test_pending_and_disabled_user_cannot_login(tmp_path, monkeypatch) -> None:
    _, engine = _setup_test_db(tmp_path, monkeypatch)
    app.dependency_overrides[get_db_session] = _override_db_session(engine)
    password_hash = AuthService._hash_password("strong-pass-123")
    with Session(bind=engine) as session:
        user_service = UserService(session)
        user_service.create_user(
            email="pending@example.com",
            display_name="Pending",
            password_hash=password_hash,
            status=UserStatus.PENDING,
        )
        user_service.create_user(
            email="disabled@example.com",
            display_name="Disabled",
            password_hash=password_hash,
            status=UserStatus.DISABLED,
        )

    client = TestClient(app)
    pending = client.post(
        "/api/auth/login",
        json={"email": "pending@example.com", "password": "strong-pass-123"},
    )
    assert pending.status_code == 401

    disabled = client.post(
        "/api/auth/login",
        json={"email": "disabled@example.com", "password": "strong-pass-123"},
    )
    assert disabled.status_code == 401
    app.dependency_overrides.clear()


def test_registration_closed_saves_access_request(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "auth-closed.sqlite3"
    monkeypatch.setenv("ASYA_DB_PATH", db_path.as_posix())
    monkeypatch.setenv("AUTH_REGISTRATION_MODE", "closed")
    monkeypatch.setenv("AUTH_SESSION_HASH_SECRET", "test-secret")
    get_settings.cache_clear()
    get_engine.cache_clear()
    settings = get_settings()
    engine = get_engine(settings.asya_db_url)
    Base.metadata.create_all(engine)
    app.dependency_overrides[get_db_session] = _override_db_session(engine)

    client = TestClient(app)
    register = client.post(
        "/api/auth/register",
        json={"email": "request@example.com", "display_name": "Req", "password": "strong-pass-123"},
    )
    assert register.status_code == 200
    assert register.json()["status"] == "request_saved"
    app.dependency_overrides.clear()
