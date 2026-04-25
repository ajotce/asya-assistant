from fastapi.testclient import TestClient

from app.main import app


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
    assert "vsellm" in payload
    assert payload["vsellm"]["api_key_configured"] is False
    assert payload["vsellm"]["base_url"] == "https://api.vsellm.ru/v1"
    assert payload["vsellm"]["reachable"] is None
    assert payload["model"]["selected"]
    assert payload["files"]["enabled"] is True
    assert payload["files"]["status"] == "готов"
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
