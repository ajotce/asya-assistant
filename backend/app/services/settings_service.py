from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.core.config import Settings
from app.db.models.user_settings import UserSettings
from app.models.schemas import SettingsResponse, SettingsUpdateRequest
from sqlalchemy.orm import Session


@dataclass
class SettingsValidationError(Exception):
    message: str


class SettingsService:
    def __init__(self, settings: Settings, db_session: Optional[Session] = None) -> None:
        self._settings = settings
        self._db_session = db_session

    def get_settings(self, *, user_id: Optional[str] = None) -> SettingsResponse:
        payload = self._default_settings_payload()
        if user_id and self._db_session is not None:
            row = self._db_session.get(UserSettings, user_id)
            if row is None:
                row = UserSettings(
                    user_id=user_id,
                    assistant_name=payload["assistant_name"],
                    system_prompt=payload["system_prompt"],
                    selected_model=payload["selected_model"],
                )
                self._db_session.add(row)
                self._db_session.flush()
            payload = {
                "assistant_name": row.assistant_name,
                "system_prompt": row.system_prompt,
                "selected_model": row.selected_model,
            }

        return SettingsResponse(
            assistant_name=payload["assistant_name"],
            system_prompt=payload["system_prompt"],
            selected_model=payload["selected_model"],
            api_key_configured=self._settings.vsellm_api_key_configured,
        )

    def update_settings(self, request: SettingsUpdateRequest, *, user_id: Optional[str] = None) -> SettingsResponse:
        if user_id is None or self._db_session is None:
            raise SettingsValidationError("Настройки пользователя недоступны без user_id.")

        assistant_name = request.assistant_name.strip()
        system_prompt = request.system_prompt.strip()
        selected_model = request.selected_model.strip()

        if not assistant_name:
            raise SettingsValidationError("Имя ассистента не должно быть пустым.")
        if not system_prompt:
            raise SettingsValidationError("Системный промт не должен быть пустым.")
        if not selected_model:
            raise SettingsValidationError("Выбранная модель не должна быть пустой.")

        row = self._db_session.get(UserSettings, user_id)
        if row is None:
            row = UserSettings(
                user_id=user_id,
                assistant_name=assistant_name,
                system_prompt=system_prompt,
                selected_model=selected_model,
            )
        else:
            row.assistant_name = assistant_name
            row.system_prompt = system_prompt
            row.selected_model = selected_model
        self._db_session.add(row)
        self._db_session.flush()

        return self.get_settings(user_id=user_id)

    def _default_settings_payload(self) -> dict:
        return {
            "assistant_name": self._settings.default_assistant_name,
            "system_prompt": self._settings.default_system_prompt,
            "selected_model": self._settings.default_chat_model,
        }
