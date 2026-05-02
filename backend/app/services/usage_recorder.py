from __future__ import annotations

from app.core.config import Settings
from app.repositories.chat_repository import ChatRepository
from app.repositories.usage_record_repository import UsageRecordRepository


class UsageRecorder:
    def __init__(
        self,
        *,
        settings: Settings,
        user_id: str,
        chat_repository: ChatRepository,
        usage_repository: UsageRecordRepository,
    ) -> None:
        self._settings = settings
        self._user_id = user_id
        self._chat_repository = chat_repository
        self._usage_repository = usage_repository

    def record_chat_usage(self, session_id: str, usage: dict | None) -> None:
        if not isinstance(usage, dict):
            return
        if self._chat_repository.get_for_user(session_id, self._user_id) is None:
            return
        prompt_tokens = self._extract_int(usage.get("prompt_tokens")) or self._extract_int(usage.get("input_tokens"))
        completion_tokens = self._extract_int(usage.get("completion_tokens")) or self._extract_int(
            usage.get("output_tokens")
        )
        total_tokens = self._extract_int(usage.get("total_tokens"))
        if total_tokens is None and prompt_tokens is not None and completion_tokens is not None:
            total_tokens = prompt_tokens + completion_tokens

        self._usage_repository.create(
            user_id=self._user_id,
            chat_id=session_id,
            kind="chat",
            model=self._safe_model_name(usage.get("model"), self._settings.default_chat_model),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
        )

    def record_embeddings_usage(self, session_id: str, usage: dict | None) -> None:
        if not isinstance(usage, dict):
            return
        if self._chat_repository.get_for_user(session_id, self._user_id) is None:
            return
        input_tokens = self._extract_int(usage.get("input_tokens")) or self._extract_int(usage.get("prompt_tokens"))
        total_tokens = self._extract_int(usage.get("total_tokens"))
        if total_tokens is None and input_tokens is not None:
            total_tokens = input_tokens

        self._usage_repository.create(
            user_id=self._user_id,
            chat_id=session_id,
            kind="embeddings",
            model=self._safe_model_name(usage.get("model"), self._settings.default_embedding_model or "unknown"),
            prompt_tokens=input_tokens,
            completion_tokens=None,
            total_tokens=total_tokens,
        )

    @staticmethod
    def _safe_model_name(value: object, fallback: str) -> str:
        if isinstance(value, str) and value.strip():
            return value.strip()[:255]
        return (fallback or "unknown")[:255]

    @staticmethod
    def _extract_int(value: object):
        if value is None or isinstance(value, bool):
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return None
            try:
                return int(float(stripped))
            except ValueError:
                return None
        return None
