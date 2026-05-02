from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from tests.auth_helpers import build_authed_client


def test_voice_settings_get_defaults(tmp_path, monkeypatch):
    monkeypatch.setenv("MASTER_ENCRYPTION_KEY", "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY=")
    client = build_authed_client(tmp_path, monkeypatch, "voice-api@example.com")

    response = client.get("/api/voice/settings")
    assert response.status_code == 200
    data = response.json()
    assert data["tts_enabled"] is False
    assert data["voice_gender"] == "female"
    assert data["stt_provider"] == "mock"
    app.dependency_overrides.clear()


def test_voice_settings_update(tmp_path, monkeypatch):
    monkeypatch.setenv("MASTER_ENCRYPTION_KEY", "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY=")
    client = build_authed_client(tmp_path, monkeypatch, "voice-update@example.com")

    response = client.put("/api/voice/settings", json={
        "assistant_name": "Asya",
        "voice_gender": "male",
        "stt_provider": "mock",
        "tts_provider": "mock",
        "tts_enabled": True,
    })
    assert response.status_code == 200
    data = response.json()
    assert data["tts_enabled"] is True
    assert data["voice_gender"] == "male"
    app.dependency_overrides.clear()


def test_voice_stt(tmp_path, monkeypatch):
    monkeypatch.setenv("MASTER_ENCRYPTION_KEY", "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY=")
    monkeypatch.setenv("VOICE_MAX_AUDIO_BYTES", "102400")
    client = build_authed_client(tmp_path, monkeypatch, "voice-stt@example.com")

    response = client.post(
        "/api/voice/stt",
        content=b"fake-audio-data",
        headers={"Content-Type": "audio/webm"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["text"] == "[mock transcript]"
    assert data["provider"] == "mock"
    app.dependency_overrides.clear()


def test_voice_stt_too_large(tmp_path, monkeypatch):
    monkeypatch.setenv("MASTER_ENCRYPTION_KEY", "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY=")
    monkeypatch.setenv("VOICE_MAX_AUDIO_BYTES", "5")
    client = build_authed_client(tmp_path, monkeypatch, "voice-big@example.com")

    response = client.post(
        "/api/voice/stt",
        content=b"too-large",
        headers={"Content-Type": "audio/webm"},
    )
    assert response.status_code == 400
    app.dependency_overrides.clear()


def test_voice_stt_unauthorized(tmp_path, monkeypatch):
    response = TestClient(app).post("/api/voice/stt", content=b"data")
    assert response.status_code == 401
    app.dependency_overrides.clear()


def test_voice_tts_returns_audio(tmp_path, monkeypatch):
    monkeypatch.setenv("MASTER_ENCRYPTION_KEY", "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY=")
    client = build_authed_client(tmp_path, monkeypatch, "voice-tts@example.com")

    response = client.post("/api/voice/tts", json={"text": "Привет"})
    assert response.status_code == 200
    assert b"MOCK_AUDIO" in response.content
    assert response.headers.get("content-type", "").startswith("audio/")
    app.dependency_overrides.clear()
