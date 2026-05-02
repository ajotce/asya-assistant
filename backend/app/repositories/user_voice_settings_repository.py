from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models.user_voice_settings import UserVoiceSettings


class UserVoiceSettingsRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, user_id: str) -> UserVoiceSettings | None:
        return self._session.get(UserVoiceSettings, user_id)

    def save(self, item: UserVoiceSettings) -> UserVoiceSettings:
        self._session.add(item)
        self._session.flush()
        return item
