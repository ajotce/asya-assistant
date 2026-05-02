from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps_auth import get_db_session
from app.core.config import get_settings
from app.db.base import Base
from app.db.models.chat import Chat
from app.db.models.common import ChatKind, UserRole, UserStatus
from app.db.models.user import User
from app.db.session import get_engine
from app.main import app
from app.repositories.user_repository import UserRepository


def _setup_test_db(tmp_path, monkeypatch):
    db_path = tmp_path / "access-requests.sqlite3"
    monkeypatch.setenv("ASYA_DB_PATH", db_path.as_posix())
    monkeypatch.setenv("AUTH_REGISTRATION_MODE", "closed")
    monkeypatch.setenv("AUTH_SESSION_HASH_SECRET", "test-secret")
    monkeypatch.setenv("AUTH_COOKIE_NAME", "asya_session")
    get_settings.cache_clear()
    get_engine.cache_clear()
    settings = get_settings()
    engine = get_engine(settings.asya_db_url)
    Base.metadata.create_all(engine)
    return engine


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


def _promote_user_to_admin(engine, email: str) -> None:
    with Session(bind=engine) as session:
        repo = UserRepository(session)
        user = repo.get_by_email(email)
        assert user is not None
        user.role = UserRole.ADMIN
        repo.save(user)
        session.commit()


def test_submit_access_request_and_repeat_is_predictable(tmp_path, monkeypatch) -> None:
    engine = _setup_test_db(tmp_path, monkeypatch)
    app.dependency_overrides[get_db_session] = _override_db_session(engine)
    client = TestClient(app)

    first = client.post("/api/access-requests", json={"email": "u@example.com", "display_name": "User"})
    assert first.status_code == 200
    request_id = first.json()["request"]["id"]
    assert first.json()["request"]["status"] == "pending"

    second = client.post("/api/access-requests", json={"email": "u@example.com", "display_name": "User 2"})
    assert second.status_code == 200
    assert second.json()["request"]["id"] == request_id
    app.dependency_overrides.clear()


def test_admin_only_endpoints_and_approve_flow(tmp_path, monkeypatch) -> None:
    engine = _setup_test_db(tmp_path, monkeypatch)
    app.dependency_overrides[get_db_session] = _override_db_session(engine)

    admin_client = TestClient(app)
    user_client = TestClient(app)

    # Проще: поднимем login-ready admin/user через open-регистрацию временно.
    monkeypatch.setenv("AUTH_REGISTRATION_MODE", "open")
    get_settings.cache_clear()
    get_engine.cache_clear()
    # Переподнимаем override на тот же engine.
    app.dependency_overrides[get_db_session] = _override_db_session(engine)

    admin_client.post(
        "/api/auth/register",
        json={"email": "a2@example.com", "display_name": "A2", "password": "strong-pass-123"},
    )
    _promote_user_to_admin(engine, "a2@example.com")
    admin_login = admin_client.post(
        "/api/auth/login",
        json={"email": "a2@example.com", "password": "strong-pass-123"},
    )
    assert admin_login.status_code == 200

    user_client.post(
        "/api/auth/register",
        json={"email": "u2@example.com", "display_name": "U2", "password": "strong-pass-123"},
    )
    user_login = user_client.post(
        "/api/auth/login",
        json={"email": "u2@example.com", "password": "strong-pass-123"},
    )
    assert user_login.status_code == 200

    submit = admin_client.post("/api/access-requests", json={"email": "beta@example.com", "display_name": "Beta"})
    request_id = submit.json()["request"]["id"]

    forbidden = user_client.get("/api/admin/access-requests")
    assert forbidden.status_code == 403

    listed = admin_client.get("/api/admin/access-requests")
    assert listed.status_code == 200
    assert any(item["id"] == request_id for item in listed.json())

    approved = admin_client.post(f"/api/admin/access-requests/{request_id}/approve")
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"
    assert approved.json()["user"]["email"] == "beta@example.com"

    with Session(bind=engine) as session:
        user = session.execute(select(User).where(User.email == "beta@example.com")).scalar_one_or_none()
        assert user is not None
        assert user.status == UserStatus.ACTIVE

        base_chats = list(
            session.execute(
                select(Chat).where(
                    Chat.user_id == user.id,
                    Chat.kind == ChatKind.BASE,
                    Chat.is_archived.is_(False),
                    Chat.is_deleted.is_(False),
                )
            ).scalars()
        )
        assert len(base_chats) == 1

    app.dependency_overrides.clear()


def test_admin_endpoints_require_auth_and_admin_role(tmp_path, monkeypatch) -> None:
    engine = _setup_test_db(tmp_path, monkeypatch)
    app.dependency_overrides[get_db_session] = _override_db_session(engine)

    anon_client = TestClient(app)
    anon = anon_client.get("/api/admin/access-requests")
    assert anon.status_code == 401

    monkeypatch.setenv("AUTH_REGISTRATION_MODE", "open")
    get_settings.cache_clear()
    get_engine.cache_clear()
    app.dependency_overrides[get_db_session] = _override_db_session(engine)

    user_client = TestClient(app)
    user_client.post(
        "/api/auth/register",
        json={"email": "plain@example.com", "display_name": "Plain", "password": "strong-pass-123"},
    )
    login = user_client.post(
        "/api/auth/login",
        json={"email": "plain@example.com", "password": "strong-pass-123"},
    )
    assert login.status_code == 200

    forbidden = user_client.get("/api/admin/access-requests")
    assert forbidden.status_code == 403
    app.dependency_overrides.clear()


def test_admin_cannot_self_approve_and_can_reject(tmp_path, monkeypatch) -> None:
    engine = _setup_test_db(tmp_path, monkeypatch)
    app.dependency_overrides[get_db_session] = _override_db_session(engine)

    monkeypatch.setenv("AUTH_REGISTRATION_MODE", "open")
    get_settings.cache_clear()
    get_engine.cache_clear()
    app.dependency_overrides[get_db_session] = _override_db_session(engine)

    client = TestClient(app)
    client.post(
        "/api/auth/register",
        json={"email": "boss@example.com", "display_name": "Boss", "password": "strong-pass-123"},
    )
    _promote_user_to_admin(engine, "boss@example.com")
    login = client.post("/api/auth/login", json={"email": "boss@example.com", "password": "strong-pass-123"})
    assert login.status_code == 200

    own_req = client.post("/api/access-requests", json={"email": "boss@example.com", "display_name": "Boss"})
    own_req_id = own_req.json()["request"]["id"]
    self_approve = client.post(f"/api/admin/access-requests/{own_req_id}/approve")
    assert self_approve.status_code == 400

    other_req = client.post("/api/access-requests", json={"email": "other@example.com", "display_name": "Other"})
    other_req_id = other_req.json()["request"]["id"]
    rejected = client.post(f"/api/admin/access-requests/{other_req_id}/reject")
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"

    app.dependency_overrides.clear()
