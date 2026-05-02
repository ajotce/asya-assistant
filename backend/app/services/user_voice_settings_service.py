from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models.common import VoiceGender, VoiceProvider
from app.db.models.user import User
from app.db.models.user_voice_settings import UserVoiceSettings
from app.repositories.user_voice_settings_repository import UserVoiceSettingsRepository


class UserVoiceSettingsService:
    def __init__(self, session: Session, settings: Settings) -> None:
        self._session = session
        self._settings = settings
        self._repo = UserVoiceSettingsRepository(session)

    def get_or_create(self, *, user: User) -> UserVoiceSettings:
        current = self._repo.get(user.id)
        if current is not None:
            return current
        created = UserVoiceSettings(
            user_id=user.id,
            assistant_name=(user.display_name or self._settings.default_assistant_name)[:120],
            voice_gender=VoiceGender.FEMALE,
            stt_provider=VoiceProvider.MOCK,
            tts_provider=VoiceProvider.MOCK,
            tts_enabled=self._settings.voice_tts_enabled_default,
        )
        self._repo.save(created)
        self._session.flush()
        return created

    def update(
        self,
        *,
        user: User,
        assistant_name: str,
        voice_gender: VoiceGender,
        stt_provider: VoiceProvider,
        tts_provider: VoiceProvider,
        tts_enabled: bool,
    ) -> UserVoiceSettings:
        settings = self.get_or_create(user=user)
        settings.assistant_name = assistant_name.strip()[:120] or self._settings.default_assistant_name
        settings.voice_gender = voice_gender
        settings.stt_provider = stt_provider
        settings.tts_provider = tts_provider
        settings.tts_enabled = tts_enabled
        self._repo.save(settings)
        self._session.flush()
        return settings
