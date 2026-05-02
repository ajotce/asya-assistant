from __future__ import annotations

from dataclasses import dataclass

import httpx

from app.core.config import Settings
from app.db.models.common import VoiceGender


class VoiceProviderError(ValueError):
    pass


@dataclass
class STTResult:
    text: str
    provider: str


@dataclass
class TTSResult:
    audio_bytes: bytes
    mime_type: str
    provider: str


class SpeechToTextProvider:
    provider_name: str

    def transcribe(self, *, audio_bytes: bytes, mime_type: str, language: str = "ru-RU") -> STTResult:
        raise NotImplementedError


class TextToSpeechProvider:
    provider_name: str

    def synthesize(self, *, text: str, language: str = "ru-RU", gender: VoiceGender = VoiceGender.FEMALE) -> TTSResult:
        raise NotImplementedError


class MockSpeechToTextProvider(SpeechToTextProvider):
    provider_name = "mock"

    def transcribe(self, *, audio_bytes: bytes, mime_type: str, language: str = "ru-RU") -> STTResult:
        if not audio_bytes:
            raise VoiceProviderError("Пустой аудио-файл.")
        return STTResult(text="[mock transcript]", provider=self.provider_name)


class MockTextToSpeechProvider(TextToSpeechProvider):
    provider_name = "mock"

    def synthesize(self, *, text: str, language: str = "ru-RU", gender: VoiceGender = VoiceGender.FEMALE) -> TTSResult:
        if not text.strip():
            raise VoiceProviderError("Пустой текст для синтеза.")
        payload = f"MOCK_AUDIO::{language}::{gender.value}::{text}".encode("utf-8")
        return TTSResult(audio_bytes=payload, mime_type="audio/wav", provider=self.provider_name)


class YandexSpeechKitSTTProvider(SpeechToTextProvider):
    provider_name = "yandex_speechkit"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def transcribe(self, *, audio_bytes: bytes, mime_type: str, language: str = "ru-RU") -> STTResult:
        api_key = self._settings.yandex_speechkit_api_key.strip()
        folder_id = self._settings.yandex_speechkit_folder_id.strip()
        if not api_key or not folder_id:
            raise VoiceProviderError("Yandex SpeechKit не настроен.")
        response = httpx.post(
            self._settings.yandex_speechkit_stt_url,
            params={"lang": language, "folderId": folder_id},
            headers={"Authorization": f"Api-Key {api_key}", "Content-Type": mime_type},
            content=audio_bytes,
            timeout=httpx.Timeout(timeout=20.0, connect=5.0),
        )
        if response.status_code >= 400:
            raise VoiceProviderError("Ошибка STT провайдера Yandex SpeechKit.")
        text = (response.json().get("result") or "").strip()
        if not text:
            raise VoiceProviderError("Yandex SpeechKit не вернул транскрипт.")
        return STTResult(text=text, provider=self.provider_name)


class YandexSpeechKitTTSProvider(TextToSpeechProvider):
    provider_name = "yandex_speechkit"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def synthesize(self, *, text: str, language: str = "ru-RU", gender: VoiceGender = VoiceGender.FEMALE) -> TTSResult:
        api_key = self._settings.yandex_speechkit_api_key.strip()
        folder_id = self._settings.yandex_speechkit_folder_id.strip()
        if not api_key or not folder_id:
            raise VoiceProviderError("Yandex SpeechKit не настроен.")
        response = httpx.post(
            self._settings.yandex_speechkit_tts_url,
            data={
                "text": text,
                "lang": language,
                "folderId": folder_id,
                "gender": "female" if gender == VoiceGender.FEMALE else "male",
                "format": "mp3",
            },
            headers={"Authorization": f"Api-Key {api_key}"},
            timeout=httpx.Timeout(timeout=20.0, connect=5.0),
        )
        if response.status_code >= 400:
            raise VoiceProviderError("Ошибка TTS провайдера Yandex SpeechKit.")
        if not response.content:
            raise VoiceProviderError("Yandex SpeechKit не вернул аудио.")
        return TTSResult(audio_bytes=response.content, mime_type="audio/mpeg", provider=self.provider_name)


class GigaChatSTTProvider(SpeechToTextProvider):
    provider_name = "gigachat"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def transcribe(self, *, audio_bytes: bytes, mime_type: str, language: str = "ru-RU") -> STTResult:
        api_key = self._settings.gigachat_api_key.strip()
        if not api_key:
            raise VoiceProviderError("GigaChat не настроен.")
        response = httpx.post(
            self._settings.gigachat_stt_url,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": mime_type},
            content=audio_bytes,
            timeout=httpx.Timeout(timeout=20.0, connect=5.0),
        )
        if response.status_code >= 400:
            raise VoiceProviderError("Ошибка STT провайдера GigaChat.")
        text = (response.json().get("text") or "").strip()
        if not text:
            raise VoiceProviderError("GigaChat не вернул транскрипт.")
        return STTResult(text=text, provider=self.provider_name)


class GigaChatTTSProvider(TextToSpeechProvider):
    provider_name = "gigachat"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def synthesize(self, *, text: str, language: str = "ru-RU", gender: VoiceGender = VoiceGender.FEMALE) -> TTSResult:
        api_key = self._settings.gigachat_api_key.strip()
        if not api_key:
            raise VoiceProviderError("GigaChat не настроен.")
        response = httpx.post(
            self._settings.gigachat_tts_url,
            json={"text": text, "voice": "jane" if gender == VoiceGender.FEMALE else "alex"},
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=httpx.Timeout(timeout=20.0, connect=5.0),
        )
        if response.status_code >= 400:
            raise VoiceProviderError("Ошибка TTS провайдера GigaChat.")
        if not response.content:
            raise VoiceProviderError("GigaChat не вернул аудио.")
        return TTSResult(audio_bytes=response.content, mime_type="audio/mpeg", provider=self.provider_name)
