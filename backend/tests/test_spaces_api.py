from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.deps_auth import get_db_session
from app.core.config import get_settings
from app.db.base import Base
from app.db.models.common import UserRole
from app.db.session import get_engine
from app.main import app
from app.repositories.user_repository import UserRepository


def _setup_test_db(tmp_path, monkeypatch):
    db_path = tmp_path / "spaces.sqlite3"
    monkeypatch.setenv("ASYA_DB_PATH", db_path.as_posix())
    monkeypatch.setenv("AUTH_REGISTRATION_MODE", "open")
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
        user = UserRepository(session).get_by_email(email)
        assert user is not None
        user.role = UserRole.ADMIN
        UserRepository(session).save(user)
        session.commit()


def _register_and_login(client: TestClient, email: str, display_name: str) -> None:
    reg = client.post(
        "/api/auth/register",
        json={"email": email, "display_name": display_name, "password": "strong-pass-123"},
    )
    assert reg.status_code == 200
    login = client.post("/api/auth/login", json={"email": email, "password": "strong-pass-123"})
    assert login.status_code == 200


def test_spaces_default_create_rename_archive_and_settings(tmp_path, monkeypatch) -> None:
    engine = _setup_test_db(tmp_path, monkeypatch)
    app.dependency_overrides[get_db_session] = _override_db_session(engine)
    client = TestClient(app)
    _register_and_login(client, "spaces-user@example.com", "Spaces User")

    listed = client.get("/api/spaces")
    assert listed.status_code == 200
    items = listed.json()
    assert len(items) == 1
    assert items[0]["is_default"] is True
    default_space_id = items[0]["id"]

    created = client.post("/api/spaces", json={"name": "Work"})
    assert created.status_code == 201
    work_space_id = created.json()["id"]

    renamed = client.patch(f"/api/spaces/{work_space_id}", json={"name": "Project X"})
    assert renamed.status_code == 200
    assert renamed.json()["name"] == "Project X"

    get_settings_resp = client.get(f"/api/spaces/{work_space_id}/settings")
    assert get_settings_resp.status_code == 200
    assert get_settings_resp.json()["memory_read_enabled"] is True

    updated = client.put(
        f"/api/spaces/{work_space_id}/settings",
        json={
            "memory_read_enabled": False,
            "memory_write_enabled": True,
            "behavior_rules_enabled": False,
            "personality_overlay_enabled": True,
        },
    )
    assert updated.status_code == 200
    assert updated.json()["memory_read_enabled"] is False
    assert updated.json()["behavior_rules_enabled"] is False

    archive_default = client.post(f"/api/spaces/{default_space_id}/archive")
    assert archive_default.status_code == 400

    archived = client.post(f"/api/spaces/{work_space_id}/archive")
    assert archived.status_code == 200
    assert archived.json()["is_archived"] is True
    app.dependency_overrides.clear()


def test_spaces_are_user_scoped(tmp_path, monkeypatch) -> None:
    engine = _setup_test_db(tmp_path, monkeypatch)
    app.dependency_overrides[get_db_session] = _override_db_session(engine)
    client_a = TestClient(app)
    client_b = TestClient(app)
    _register_and_login(client_a, "space-a@example.com", "A")
    _register_and_login(client_b, "space-b@example.com", "B")

    created = client_a.post("/api/spaces", json={"name": "A-only"})
    assert created.status_code == 201
    space_id = created.json()["id"]

    get_by_b = client_b.get(f"/api/spaces/{space_id}/settings")
    assert get_by_b.status_code == 404

    rename_by_b = client_b.patch(f"/api/spaces/{space_id}", json={"name": "Hacked"})
    assert rename_by_b.status_code == 404

    archive_by_b = client_b.post(f"/api/spaces/{space_id}/archive")
    assert archive_by_b.status_code == 404
    app.dependency_overrides.clear()


def test_admin_sees_asya_dev_regular_user_does_not_and_cannot_create(tmp_path, monkeypatch) -> None:
    engine = _setup_test_db(tmp_path, monkeypatch)
    app.dependency_overrides[get_db_session] = _override_db_session(engine)

    user_client = TestClient(app)
    _register_and_login(user_client, "plain-space@example.com", "Plain")

    user_spaces = user_client.get("/api/spaces")
    assert user_spaces.status_code == 200
    assert not any(item["name"] == "Asya-dev" for item in user_spaces.json())

    user_create_dev = user_client.post("/api/spaces", json={"name": "Asya-dev"})
    assert user_create_dev.status_code == 400

    admin_client = TestClient(app)
    _register_and_login(admin_client, "admin-space@example.com", "Admin")
    _promote_user_to_admin(engine, "admin-space@example.com")
    relogin = admin_client.post("/api/auth/login", json={"email": "admin-space@example.com", "password": "strong-pass-123"})
    assert relogin.status_code == 200

    admin_spaces = admin_client.get("/api/spaces")
    assert admin_spaces.status_code == 200
    asya_dev = next((item for item in admin_spaces.json() if item["name"] == "Asya-dev"), None)
    assert asya_dev is not None
    assert asya_dev["is_admin_only"] is True

    archive_dev = admin_client.post(f"/api/spaces/{asya_dev['id']}/archive")
    assert archive_dev.status_code == 400

    rename_dev = admin_client.patch(f"/api/spaces/{asya_dev['id']}", json={"name": "Dev2"})
    assert rename_dev.status_code == 400
    app.dependency_overrides.clear()


def test_create_chat_in_space(tmp_path, monkeypatch) -> None:
    engine = _setup_test_db(tmp_path, monkeypatch)
    app.dependency_overrides[get_db_session] = _override_db_session(engine)
    client = TestClient(app)
    _register_and_login(client, "space-chat@example.com", "Space Chat")

    created_space = client.post("/api/spaces", json={"name": "Work"})
    assert created_space.status_code == 201
    space_id = created_space.json()["id"]

    created_chat = client.post("/api/chats", json={"title": "Task chat", "space_id": space_id})
    assert created_chat.status_code == 201
    assert created_chat.json()["space_id"] == space_id

    bad_chat = client.post("/api/chats", json={"title": "Bad", "space_id": "foreign-space-id"})
    assert bad_chat.status_code == 404
    app.dependency_overrides.clear()


def test_space_activity_events_are_user_scoped(tmp_path, monkeypatch) -> None:
    engine = _setup_test_db(tmp_path, monkeypatch)
    app.dependency_overrides[get_db_session] = _override_db_session(engine)

    client_a = TestClient(app)
    client_b = TestClient(app)
    _register_and_login(client_a, "space-activity-a@example.com", "A")
    _register_and_login(client_b, "space-activity-b@example.com", "B")

    created = client_a.post("/api/spaces", json={"name": "Planning"})
    assert created.status_code == 201
    space_id = created.json()["id"]

    settings = client_a.put(
        f"/api/spaces/{space_id}/settings",
        json={
            "memory_read_enabled": True,
            "memory_write_enabled": False,
            "behavior_rules_enabled": True,
            "personality_overlay_enabled": True,
        },
    )
    assert settings.status_code == 200

    logs_a = client_a.get("/api/activity-log")
    assert logs_a.status_code == 200
    events_a = {item["event_type"] for item in logs_a.json()}
    assert "space_created" in events_a
    assert "space_updated" in events_a

    logs_b = client_b.get("/api/activity-log")
    assert logs_b.status_code == 200
    assert all(item.get("space_id") != space_id for item in logs_b.json())
    app.dependency_overrides.clear()
