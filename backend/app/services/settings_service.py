from __future__ import annotations

from dataclasses import dataclass

from app.core.config import Settings
from app.models.schemas import SettingsResponse, SettingsUpdateRequest
from app.storage.sqlite import SQLiteStorage


@dataclass
class SettingsValidationError(Exception):
    message: str


class SettingsService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._storage = SQLiteStorage(settings.sqlite_path)
        self._init_schema()

    def get_settings(self) -> SettingsResponse:
        with self._storage.connect() as conn:
            row = conn.execute(
                """
                SELECT assistant_name, system_prompt, selected_model
                FROM settings
                WHERE id = 1
                """
            ).fetchone()

            if row is None:
                defaults = self._default_settings_payload()
                conn.execute(
                    """
                    INSERT INTO settings (id, assistant_name, system_prompt, selected_model)
                    VALUES (1, ?, ?, ?)
                    """,
                    (
                        defaults["assistant_name"],
                        defaults["system_prompt"],
                        defaults["selected_model"],
                    ),
                )
                conn.commit()
                payload = defaults
            else:
                payload = {
                    "assistant_name": row["assistant_name"],
                    "system_prompt": row["system_prompt"],
                    "selected_model": row["selected_model"],
                }

        return SettingsResponse(
            assistant_name=payload["assistant_name"],
            system_prompt=payload["system_prompt"],
            selected_model=payload["selected_model"],
            api_key_configured=self._settings.vsellm_api_key_configured,
        )

    def update_settings(self, request: SettingsUpdateRequest) -> SettingsResponse:
        assistant_name = request.assistant_name.strip()
        system_prompt = request.system_prompt.strip()
        selected_model = request.selected_model.strip()

        if not assistant_name:
            raise SettingsValidationError("Имя ассистента не должно быть пустым.")
        if not system_prompt:
            raise SettingsValidationError("Системный промт не должен быть пустым.")
        if not selected_model:
            raise SettingsValidationError("Выбранная модель не должна быть пустой.")

        with self._storage.connect() as conn:
            conn.execute(
                """
                INSERT INTO settings (id, assistant_name, system_prompt, selected_model)
                VALUES (1, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                  assistant_name = excluded.assistant_name,
                  system_prompt = excluded.system_prompt,
                  selected_model = excluded.selected_model
                """,
                (assistant_name, system_prompt, selected_model),
            )
            conn.commit()

        return self.get_settings()

    def _init_schema(self) -> None:
        with self._storage.connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS settings (
                  id INTEGER PRIMARY KEY CHECK (id = 1),
                  assistant_name TEXT NOT NULL,
                  system_prompt TEXT NOT NULL,
                  selected_model TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def _default_settings_payload(self) -> dict:
        return {
            "assistant_name": self._settings.default_assistant_name,
            "system_prompt": self._settings.default_system_prompt,
            "selected_model": self._settings.default_chat_model,
        }
