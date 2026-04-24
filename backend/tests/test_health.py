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
