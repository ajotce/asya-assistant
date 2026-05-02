from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.deps_auth import get_db_session
from app.main import app
from tests.auth_helpers import build_authed_client


def test_telegram_status_not_linked(tmp_path, monkeypatch):
    monkeypatch.setenv("MASTER_ENCRYPTION_KEY", "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY=")
    monkeypatch.setenv("TELEGRAM_BOT_USERNAME", "asya_test_bot")
    client = build_authed_client(tmp_path, monkeypatch, "tg-api@example.com")

    response = client.get("/api/integrations/telegram/status")
    assert response.status_code == 200
    data = response.json()
    assert data["is_linked"] is False
    app.dependency_overrides.clear()


def test_telegram_create_link_token(tmp_path, monkeypatch):
    monkeypatch.setenv("MASTER_ENCRYPTION_KEY", "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY=")
    monkeypatch.setenv("TELEGRAM_BOT_USERNAME", "asya_test_bot")
    client = build_authed_client(tmp_path, monkeypatch, "tg-link@example.com")

    response = client.post("/api/integrations/telegram/link-token")
    assert response.status_code == 200
    data = response.json()
    assert "one_time_token" in data
    assert "bot_start_url" in data
    assert "?start=" in data["bot_start_url"]
    app.dependency_overrides.clear()


def test_telegram_unlink_when_not_linked(tmp_path, monkeypatch):
    monkeypatch.setenv("MASTER_ENCRYPTION_KEY", "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY=")
    monkeypatch.setenv("TELEGRAM_BOT_USERNAME", "asya_test_bot")
    client = build_authed_client(tmp_path, monkeypatch, "tg-unlink@example.com")

    response = client.post("/api/integrations/telegram/unlink")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["unlinked"] is False
    app.dependency_overrides.clear()


def test_telegram_api_requires_auth(tmp_path, monkeypatch):
    unauthed = TestClient(app)
    assert unauthed.get("/api/integrations/telegram/status").status_code == 401
    assert unauthed.post("/api/integrations/telegram/link-token").status_code == 401
    assert unauthed.post("/api/integrations/telegram/unlink").status_code == 401
    app.dependency_overrides.clear()
