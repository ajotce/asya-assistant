from fastapi.testclient import TestClient

from app.main import app
from app.core.config import get_settings


def test_health_returns_200() -> None:
    client = TestClient(app)
    response = client.get("/api/health")
    assert response.status_code == 200


def test_health_payload_shape() -> None:
    client = TestClient(app)
    response = client.get("/api/health")
    payload = response.json()

    assert payload["status"] == "ok"
    assert payload["version"] == "0.1.0"
    assert payload["environment"] == "local"
    assert isinstance(payload["uptime_seconds"], int)
    assert payload["uptime_seconds"] >= 0
    assert "vsellm" in payload
    assert payload["vsellm"]["api_key_configured"] is False
    assert payload["vsellm"]["base_url"] == "https://api.vsellm.ru/v1"
    assert payload["vsellm"]["reachable"] is None
    assert payload["model"]["selected"]
    assert payload["files"]["enabled"] is True
    assert payload["files"]["status"] == "готов"
    assert payload["embeddings"]["enabled"] is True
    assert payload["embeddings"]["status"] == "не настроен"
    assert "model" in payload["embeddings"]
    assert payload["storage"]["session_store"] == "готов"
    assert payload["storage"]["file_store"] == "готов"
    assert isinstance(payload["storage"]["writable"], bool)
    assert payload["storage"]["tmp_dir"]
    assert payload["session"]["enabled"] is True
    assert isinstance(payload["session"]["active_sessions"], int)
    assert payload["last_error"] is None


def test_health_reflects_active_sessions_count() -> None:
    client = TestClient(app)
    created = client.post("/api/session")
    assert created.status_code == 201
    session_id = created.json()["session_id"]

    health = client.get("/api/health")
    assert health.status_code == 200
    active_count = health.json()["session"]["active_sessions"]
    assert active_count >= 1

    deleted = client.delete(f"/api/session/{session_id}")
    assert deleted.status_code == 204


def test_health_happy_path_with_vsellm_reachable(monkeypatch) -> None:
    settings = get_settings()
    original_key = settings.vsellm_api_key
    original_embedding = settings.default_embedding_model
    settings.vsellm_api_key = "test-key"
    settings.default_embedding_model = "text-embedding-3-small"
    monkeypatch.setattr("app.api.routes_health.check_vsellm_reachable", lambda: (True, None))
    try:
        client = TestClient(app)
        payload = client.get("/api/health").json()
    finally:
        settings.vsellm_api_key = original_key
        settings.default_embedding_model = original_embedding

    assert payload["status"] == "ok"
    assert payload["vsellm"]["api_key_configured"] is True
    assert payload["vsellm"]["reachable"] is True
    assert payload["embeddings"]["status"] == "готов"
    assert payload["embeddings"]["last_error"] is None
