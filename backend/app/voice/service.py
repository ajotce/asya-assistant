from __future__ import annotations

from dataclasses import dataclass

from app.core.config import Settings
from app.db.models.common import VoiceGender, VoiceProvider
from app.db.models.user import User
from app.services.user_voice_settings_service import UserVoiceSettingsService
from app.voice.providers import (
    GigaChatSTTProvider,
    GigaChatTTSProvider,
    MockSpeechToTextProvider,
    MockTextToSpeechProvider,
    SpeechToTextProvider,
    STTResult,
    TextToSpeechProvider,
    TTSResult,
    VoiceProviderError,
    YandexSpeechKitSTTProvider,
    YandexSpeechKitTTSProvider,
)


class VoiceValidationError(ValueError):
    pass


@dataclass
class VoiceTranscriptionResponse:
    text: str
    provider: str


@dataclass
class VoiceSynthesisResponse:
    audio_bytes: bytes
    mime_type: str
    provider: str


class VoiceService:
    def __init__(self, settings: Settings, voice_settings_service: UserVoiceSettingsService) -> None:
        self._settings = settings
        self._voice_settings_service = voice_settings_service

    def transcribe(self, *, user: User, audio_bytes: bytes, mime_type: str) -> VoiceTranscriptionResponse:
        if not audio_bytes:
            raise VoiceValidationError("Аудио-файл пуст.")
        if len(audio_bytes) > self._settings.voice_max_audio_bytes:
            raise VoiceValidationError("Размер аудио превышает допустимый лимит.")

        user_voice = self._voice_settings_service.get_or_create(user=user)
        provider = self._stt_provider(user_voice.stt_provider)
        result: STTResult = provider.transcribe(audio_bytes=audio_bytes, mime_type=mime_type)
        return VoiceTranscriptionResponse(text=result.text, provider=result.provider)

    def synthesize(self, *, user: User, text: str) -> VoiceSynthesisResponse:
        if not text.strip():
            raise VoiceValidationError("Текст для синтеза пуст.")
        user_voice = self._voice_settings_service.get_or_create(user=user)
        provider = self._tts_provider(user_voice.tts_provider)
        result: TTSResult = provider.synthesize(text=text, gender=user_voice.voice_gender)
        return VoiceSynthesisResponse(
            audio_bytes=result.audio_bytes,
            mime_type=result.mime_type,
            provider=result.provider,
        )

    def _stt_provider(self, provider: VoiceProvider) -> SpeechToTextProvider:
        if provider == VoiceProvider.YANDEX_SPEECHKIT:
            return YandexSpeechKitSTTProvider(self._settings)
        if provider == VoiceProvider.GIGACHAT:
            return GigaChatSTTProvider(self._settings)
        if provider == VoiceProvider.MOCK:
            return MockSpeechToTextProvider()
        raise VoiceProviderError("Неподдерживаемый STT-провайдер.")

    def _tts_provider(self, provider: VoiceProvider) -> TextToSpeechProvider:
        if provider == VoiceProvider.YANDEX_SPEECHKIT:
            return YandexSpeechKitTTSProvider(self._settings)
        if provider == VoiceProvider.GIGACHAT:
            return GigaChatTTSProvider(self._settings)
        if provider == VoiceProvider.MOCK:
            return MockTextToSpeechProvider()
        raise VoiceProviderError("Неподдерживаемый TTS-провайдер.")


def parse_voice_gender(raw: str) -> VoiceGender:
    try:
        return VoiceGender(raw)
    except ValueError as exc:
        raise VoiceValidationError("Неподдерживаемое значение voice_gender.") from exc


def parse_voice_provider(raw: str) -> VoiceProvider:
    try:
        return VoiceProvider(raw)
    except ValueError as exc:
        raise VoiceValidationError("Неподдерживаемый voice provider.") from exc
