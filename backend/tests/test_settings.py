from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.services.settings_service import SettingsService


class FakeEnvSettings:
    def __init__(self, db_path: Path, api_key: str = "") -> None:
        self.sqlite_path = db_path.as_posix()
        self.default_assistant_name = "Asya"
        self.default_system_prompt = "Default system prompt"
        self.default_chat_model = "openai/gpt-5"
        self.vsellm_api_key = api_key

    @property
    def vsellm_api_key_configured(self) -> bool:
        return bool(self.vsellm_api_key.strip())


def test_get_settings_returns_defaults_and_hides_api_key(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "settings-defaults.sqlite3"
    service = SettingsService(FakeEnvSettings(db_path=db_path, api_key="secret-key"))
    monkeypatch.setattr("app.api.routes_settings.get_settings_service", lambda: service)

    response = TestClient(app).get("/api/settings")
    assert response.status_code == 200
    payload = response.json()
    assert payload["assistant_name"] == "Asya"
    assert payload["system_prompt"] == "Default system prompt"
    assert payload["selected_model"] == "openai/gpt-5"
    assert payload["api_key_configured"] is True
    assert "vsellm_api_key" not in payload


def test_put_settings_updates_values(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "settings-update.sqlite3"
    service = SettingsService(FakeEnvSettings(db_path=db_path))
    monkeypatch.setattr("app.api.routes_settings.get_settings_service", lambda: service)
    client = TestClient(app)

    update = {
        "assistant_name": "Ася",
        "system_prompt": "Ты помогаешь кратко и по делу.",
        "selected_model": "openai/gpt-5-mini",
    }
    put_resp = client.put("/api/settings", json=update)
    assert put_resp.status_code == 200
    assert put_resp.json()["assistant_name"] == "Ася"
    assert put_resp.json()["selected_model"] == "openai/gpt-5-mini"

    get_resp = client.get("/api/settings")
    assert get_resp.status_code == 200
    saved = get_resp.json()
    assert saved["assistant_name"] == "Ася"
    assert saved["system_prompt"] == "Ты помогаешь кратко и по делу."
    assert saved["selected_model"] == "openai/gpt-5-mini"


def test_put_settings_validation_error(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "settings-validation.sqlite3"
    service = SettingsService(FakeEnvSettings(db_path=db_path))
    monkeypatch.setattr("app.api.routes_settings.get_settings_service", lambda: service)
    client = TestClient(app)

    response = client.put(
        "/api/settings",
        json={"assistant_name": "  ", "system_prompt": "ok", "selected_model": "openai/gpt-5"},
    )
    assert response.status_code == 400
    assert "не должно быть пустым" in response.json()["detail"]


def test_put_settings_rejects_unknown_fields(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "settings-unknown.sqlite3"
    service = SettingsService(FakeEnvSettings(db_path=db_path))
    monkeypatch.setattr("app.api.routes_settings.get_settings_service", lambda: service)
    client = TestClient(app)

    response = client.put(
        "/api/settings",
        json={
            "assistant_name": "Asya",
            "system_prompt": "ok",
            "selected_model": "openai/gpt-5",
            "vsellm_api_key": "forbidden",
        },
    )
    assert response.status_code == 422
