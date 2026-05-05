from fastapi.testclient import TestClient

from app.api.deps_auth import get_db_session
from app.main import app
from tests.auth_helpers import override_db_session, setup_test_db


def _build_authed_client(tmp_path, monkeypatch, email: str) -> TestClient:
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


def test_get_settings_requires_auth(tmp_path, monkeypatch) -> None:
    _, engine = setup_test_db(tmp_path, monkeypatch)
    app.dependency_overrides[get_db_session] = override_db_session(engine)
    client = TestClient(app)
    response = client.get("/api/settings")
    assert response.status_code == 401
    app.dependency_overrides.clear()


def test_get_settings_returns_defaults_for_user(tmp_path, monkeypatch) -> None:
    client = _build_authed_client(tmp_path, monkeypatch, "user@example.com")
    response = client.get("/api/settings")
    assert response.status_code == 200
    payload = response.json()
    assert payload["assistant_name"] == "Asya"
    assert payload["selected_model"] == "openai/gpt-5"
    assert payload["default_storage_provider"] == "google_drive"
    assert payload["default_storage_folders"] == {}
    assert payload["api_key_configured"] is False
    app.dependency_overrides.clear()


def test_put_settings_updates_only_current_user(tmp_path, monkeypatch) -> None:
    _, engine = setup_test_db(tmp_path, monkeypatch)
    app.dependency_overrides[get_db_session] = override_db_session(engine)
    user_a = TestClient(app)
    user_b = TestClient(app)

    user_a.post("/api/auth/register", json={"email": "a@example.com", "display_name": "A", "password": "strong-pass-123"})
    user_b.post("/api/auth/register", json={"email": "b@example.com", "display_name": "B", "password": "strong-pass-123"})
    user_a.post("/api/auth/login", json={"email": "a@example.com", "password": "strong-pass-123"})
    user_b.post("/api/auth/login", json={"email": "b@example.com", "password": "strong-pass-123"})

    update = {
        "assistant_name": "Ася A",
        "system_prompt": "Промт A",
        "selected_model": "openai/gpt-5-mini",
        "default_storage_provider": "onedrive",
        "default_storage_folders": {"onedrive": "/docs"},
    }
    put_resp = user_a.put("/api/settings", json=update)
    assert put_resp.status_code == 200

    get_a = user_a.get("/api/settings")
    assert get_a.status_code == 200
    assert get_a.json()["assistant_name"] == "Ася A"
    assert get_a.json()["default_storage_provider"] == "onedrive"

    get_b = user_b.get("/api/settings")
    assert get_b.status_code == 200
    assert get_b.json()["assistant_name"] == "Asya"
    assert get_b.json()["selected_model"] == "openai/gpt-5"
    assert get_b.json()["default_storage_provider"] == "google_drive"
    app.dependency_overrides.clear()


def test_put_settings_validation_error(tmp_path, monkeypatch) -> None:
    client = _build_authed_client(tmp_path, monkeypatch, "validation@example.com")
    response = client.put(
        "/api/settings",
        json={
            "assistant_name": "  ",
            "system_prompt": "ok",
            "selected_model": "openai/gpt-5",
            "default_storage_provider": "google_drive",
            "default_storage_folders": {},
        },
    )
    assert response.status_code == 400
    assert "не должно быть пустым" in response.json()["detail"]
    app.dependency_overrides.clear()


def test_put_settings_rejects_unknown_fields(tmp_path, monkeypatch) -> None:
    client = _build_authed_client(tmp_path, monkeypatch, "unknown@example.com")
    response = client.put(
        "/api/settings",
        json={
            "assistant_name": "Asya",
            "system_prompt": "ok",
            "selected_model": "openai/gpt-5",
            "default_storage_provider": "google_drive",
            "default_storage_folders": {},
            "vsellm_api_key": "forbidden",
        },
    )
    assert response.status_code == 422
    app.dependency_overrides.clear()
