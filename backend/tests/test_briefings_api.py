from __future__ import annotations

from unittest.mock import patch

from app.main import app
from tests.auth_helpers import build_authed_client


def test_briefings_settings_and_generate_archive(tmp_path, monkeypatch):
    monkeypatch.setenv("MASTER_ENCRYPTION_KEY", "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY=")
    monkeypatch.setenv("TELEGRAM_BOT_USERNAME", "asya_test_bot")
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://asya.local")
    client = build_authed_client(tmp_path, monkeypatch, "briefings@example.com")

    settings_response = client.get("/api/briefings/settings")
    assert settings_response.status_code == 200
    assert settings_response.json()["morning_enabled"] is True

    patch_response = client.patch(
        "/api/briefings/settings",
        json={
            "morning_enabled": True,
            "evening_enabled": False,
            "delivery_in_app": True,
            "delivery_telegram": False,
        },
    )
    assert patch_response.status_code == 200
    assert patch_response.json()["evening_enabled"] is False

    generate_response = client.post("/api/briefings/generate", json={"kind": "morning"})
    assert generate_response.status_code == 200
    payload = generate_response.json()
    assert payload["status"] == "ok"
    assert payload["briefing"]["kind"] == "morning"
    assert "# Утро" in payload["briefing"]["content_markdown"]

    archive_response = client.get("/api/briefings/archive")
    assert archive_response.status_code == 200
    archive = archive_response.json()
    assert len(archive) == 1
    assert archive[0]["kind"] == "morning"

    item_response = client.get(f"/api/briefings/{archive[0]['id']}")
    assert item_response.status_code == 200
    assert "## Главное" in item_response.json()["content_markdown"]
    app.dependency_overrides.clear()


def test_briefings_telegram_delivery_uses_sender_and_no_diary_when_disabled(tmp_path, monkeypatch):
    monkeypatch.setenv("MASTER_ENCRYPTION_KEY", "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY=")
    monkeypatch.setenv("TELEGRAM_BOT_USERNAME", "asya_test_bot")
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://asya.local")
    client = build_authed_client(tmp_path, monkeypatch, "briefings-telegram@example.com")

    diary_patch = client.patch(
        "/api/diary/settings",
        json={
            "briefing_enabled": False,
            "search_enabled": True,
            "memories_enabled": True,
            "evening_prompt_enabled": True,
        },
    )
    assert diary_patch.status_code == 200

    settings_patch = client.patch(
        "/api/briefings/settings",
        json={
            "morning_enabled": True,
            "evening_enabled": True,
            "delivery_in_app": True,
            "delivery_telegram": True,
        },
    )
    assert settings_patch.status_code == 200

    with patch("app.integrations.telegram.bot_sender.TelegramBotSender.send_notification", return_value=True) as send_mock:
        response = client.post("/api/briefings/generate", json={"kind": "evening"})

    assert response.status_code == 200
    body = response.json()["briefing"]
    assert body["delivered_telegram"] is True
    assert "Раздел дневника отключён" in body["content_markdown"]
    send_mock.assert_called_once()
    kwargs = send_mock.call_args.kwargs
    assert kwargs["button_text"] == "Открыть в Asya"
    assert kwargs["button_url"].endswith("/briefings")
    app.dependency_overrides.clear()
