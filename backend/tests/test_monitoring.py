from __future__ import annotations

import base64

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import create_app


def _basic_auth(username: str, password: str) -> dict[str, str]:
    token = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("utf-8")
    return {"Authorization": f"Basic {token}"}


def test_metrics_endpoint_returns_prometheus_payload(monkeypatch) -> None:
    settings = get_settings()
    settings.metrics_enabled = True
    settings.metrics_basic_auth_username = "metrics"
    settings.metrics_basic_auth_password = "secret"

    client = TestClient(create_app())
    response = client.get(
        settings.metrics_path,
        headers=_basic_auth("metrics", "secret"),
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert "http_requests_total" in response.text


def test_metrics_endpoint_requires_auth(monkeypatch) -> None:
    settings = get_settings()
    settings.metrics_enabled = True
    settings.metrics_basic_auth_username = "metrics"
    settings.metrics_basic_auth_password = "secret"

    client = TestClient(create_app())
    response = client.get(settings.metrics_path)

    assert response.status_code == 401


def test_sentry_before_send_sanitizes_payload_and_test_route(monkeypatch) -> None:
    settings = get_settings()
    settings.sentry_dsn = "https://public@example.com/1"
    settings.enable_test_routes = True

    captured: dict[str, object] = {}

    def fake_sentry_init(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr("app.main.sentry_init", fake_sentry_init)

    app = create_app()
    client = TestClient(app, raise_server_exceptions=False)

    response = client.get("/api/test/sentry")
    assert response.status_code == 500

    before_send = captured.get("before_send")
    assert callable(before_send)

    sample_event = {
        "request": {
            "data": "raw-body",
            "cookies": {"session": "secret"},
            "headers": {
                "Authorization": "Bearer secret-token",
                "X-Request-ID": "abc",
            },
        },
        "extra": {
            "access_token": "secret-value",
            "safe": "ok",
        },
    }
    sanitized = before_send(sample_event, {})

    request_payload = sanitized["request"]
    assert "data" not in request_payload
    assert "cookies" not in request_payload
    assert request_payload["headers"]["Authorization"] == "[REDACTED]"
    assert sanitized["extra"]["access_token"] == "[REDACTED]"
    assert sanitized["extra"]["safe"] == "ok"
