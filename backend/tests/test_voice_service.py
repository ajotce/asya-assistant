from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.base import Base
from app.db.models.common import VoiceGender, VoiceProvider
from app.db.models.user import User
from app.db.session import get_engine
from app.services.user_voice_settings_service import UserVoiceSettingsService
from app.voice.providers import (
    MockSpeechToTextProvider,
    MockTextToSpeechProvider,
    VoiceProviderError,
)
from app.voice.service import VoiceService, VoiceValidationError


@pytest.fixture
def test_session(tmp_path, monkeypatch):
    db_path = tmp_path / "voice-test.sqlite3"
    monkeypatch.setenv("ASYA_DB_PATH", db_path.as_posix())
    monkeypatch.setenv("VOICE_MAX_AUDIO_BYTES", "10240")
    get_settings.cache_clear()
    get_engine.cache_clear()
    settings = get_settings()
    engine = get_engine(settings.asya_db_url)
    Base.metadata.create_all(engine)
    session = Session(bind=engine)
    yield session
    session.close()
    get_settings.cache_clear()
    get_engine.cache_clear()


def _create_user(session: Session, user_id: str = "test-user-1") -> User:
    user = User(id=user_id, email=f"{user_id}@test.com", display_name="Test", role="user", status="active")
    session.add(user)
    session.flush()
    return user


def test_mock_stt(test_session):
    provider = MockSpeechToTextProvider()
    result = provider.transcribe(audio_bytes=b"fake-audio", mime_type="audio/webm")
    assert result.text == "[mock transcript]"
    assert result.provider == "mock"


def test_mock_tts(test_session):
    provider = MockTextToSpeechProvider()
    result = provider.synthesize(text="Привет")
    assert b"MOCK_AUDIO" in result.audio_bytes
    assert result.mime_type == "audio/wav"
    assert result.provider == "mock"


def test_voice_service_transcribe(test_session):
    session = test_session
    settings = get_settings()
    user = _create_user(session)
    voice_settings = UserVoiceSettingsService(session, settings)
    voice_settings.get_or_create(user=user)
    session.flush()

    voice = VoiceService(settings, voice_settings)
    result = voice.transcribe(user=user, audio_bytes=b"fake-audio", mime_type="audio/webm")
    assert result.text == "[mock transcript]"
    assert result.provider == "mock"


def test_voice_service_transcribe_too_large(test_session):
    session = test_session
    settings = get_settings()
    user = _create_user(session)
    voice_settings = UserVoiceSettingsService(session, settings)
    voice_settings.get_or_create(user=user)
    session.flush()

    voice = VoiceService(settings, voice_settings)
    large_audio = b"x" * 20000
    with pytest.raises(VoiceValidationError, match="лимит"):
        voice.transcribe(user=user, audio_bytes=large_audio, mime_type="audio/webm")


def test_voice_service_synthesize(test_session):
    session = test_session
    settings = get_settings()
    user = _create_user(session)
    voice_settings = UserVoiceSettingsService(session, settings)
    voice_settings.get_or_create(user=user)
    session.flush()

    voice = VoiceService(settings, voice_settings)
    result = voice.synthesize(user=user, text="Привет")
    assert b"MOCK_AUDIO" in result.audio_bytes
    assert result.mime_type == "audio/wav"
    assert result.provider == "mock"


def test_voice_service_synthesize_empty_text(test_session):
    session = test_session
    settings = get_settings()
    user = _create_user(session)
    voice_settings = UserVoiceSettingsService(session, settings)
    voice_settings.get_or_create(user=user)
    session.flush()

    voice = VoiceService(settings, voice_settings)
    with pytest.raises(VoiceValidationError):
        voice.synthesize(user=user, text="")


def test_user_voice_settings_update(test_session):
    session = test_session
    settings = get_settings()
    user = _create_user(session)
    service = UserVoiceSettingsService(session, settings)

    updated = service.update(
        user=user,
        assistant_name="Asya",
        voice_gender=VoiceGender.MALE,
        stt_provider=VoiceProvider.MOCK,
        tts_provider=VoiceProvider.MOCK,
        tts_enabled=True,
    )
    assert updated.voice_gender == VoiceGender.MALE
    assert updated.tts_enabled is True
    assert updated.assistant_name == "Asya"


def test_voice_provider_error_empty_audio():
    provider = MockSpeechToTextProvider()
    with pytest.raises(VoiceProviderError):
        provider.transcribe(audio_bytes=b"", mime_type="audio/webm")


def test_mock_tts_empty_text():
    provider = MockTextToSpeechProvider()
    with pytest.raises(VoiceProviderError):
        provider.synthesize(text="")


def test_default_settings_created(test_session):
    session = test_session
    settings = get_settings()
    user = _create_user(session, "new-user-2")
    service = UserVoiceSettingsService(session, settings)
    created = service.get_or_create(user=user)
    assert created.voice_gender == VoiceGender.FEMALE
    assert created.stt_provider == VoiceProvider.MOCK
