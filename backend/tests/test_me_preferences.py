from fastapi.testclient import TestClient

from app.api.deps_auth import get_db_session
from app.main import app
from tests.auth_helpers import override_db_session, setup_test_db


def _authed_client(tmp_path, monkeypatch, email: str) -> TestClient:
    _, engine = setup_test_db(tmp_path, monkeypatch)
    app.dependency_overrides[get_db_session] = override_db_session(engine)
    client = TestClient(app)
    register = client.post(
        "/api/auth/register",
        json={"email": email, "display_name": "User", "password": "strong-pass-123"},
    )
    assert register.status_code == 200
    login = client.post("/api/auth/login", json={"email": email, "password": "strong-pass-123"})
    assert login.status_code == 200
    return client


def test_get_me_preferences_defaults(tmp_path, monkeypatch):
    client = _authed_client(tmp_path, monkeypatch, "prefs@example.com")
    response = client.get("/api/me/preferences")
    assert response.status_code == 200
    data = response.json()
    assert data["wakeword_enabled"] is False
    assert data["wakeword_phrase"] == "ася"
    assert data["wakeword_sensitivity"] == 0.5
    app.dependency_overrides.clear()


def test_patch_me_preferences(tmp_path, monkeypatch):
    client = _authed_client(tmp_path, monkeypatch, "prefs-update@example.com")
    response = client.patch(
        "/api/me/preferences",
        json={"wakeword_enabled": True, "wakeword_phrase": "асья", "wakeword_sensitivity": 0.7},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["wakeword_enabled"] is True
    assert data["wakeword_phrase"] == "асья"
    assert data["wakeword_sensitivity"] == 0.7

    check = client.get("/api/me/preferences")
    assert check.status_code == 200
    assert check.json()["wakeword_enabled"] is True
    app.dependency_overrides.clear()
