from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models.common import ActivityEntityType, ActivityEventType
from app.db.models.diary_entry import DiaryEntry
from app.db.models.diary_settings import DiarySettings
from app.db.models.user import User
from app.repositories.activity_log_repository import ActivityLogRepository
from app.repositories.diary_entry_repository import DiaryEntryRepository
from app.repositories.diary_settings_repository import DiarySettingsRepository


class DiaryNotFoundError(ValueError):
    pass


@dataclass
class DiarySettingsPatch:
    briefing_enabled: bool
    search_enabled: bool
    memories_enabled: bool
    evening_prompt_enabled: bool


class DiaryService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._settings_repo = DiarySettingsRepository(session)
        self._entries = DiaryEntryRepository(session)
        self._activity = ActivityLogRepository(session)
        self._settings = get_settings()

    def get_settings(self, user: User) -> DiarySettings:
        return self._settings_repo.get_or_create_default(user.id)

    def patch_settings(self, user: User, patch: DiarySettingsPatch) -> DiarySettings:
        item = self._settings_repo.get_or_create_default(user.id)
        item.briefing_enabled = patch.briefing_enabled
        item.search_enabled = patch.search_enabled
        item.memories_enabled = patch.memories_enabled
        item.evening_prompt_enabled = patch.evening_prompt_enabled
        self._settings_repo.save(item)
        self._session.commit()
        self._session.refresh(item)
        return item

    def list_entries(self, user: User, *, query: str | None = None, limit: int = 100) -> list[DiaryEntry]:
        return self._entries.list_for_user(user.id, query=query, limit=limit)

    def get_entry(self, user: User, entry_id: str) -> DiaryEntry:
        item = self._entries.get_for_user(entry_id, user.id)
        if item is None:
            raise DiaryNotFoundError("Запись дневника не найдена.")
        return item

    def create_entry(
        self,
        *,
        user: User,
        title: str,
        content: str,
        audio_bytes: bytes | None = None,
        audio_filename: str | None = None,
    ) -> DiaryEntry:
        audio_path = None
        if audio_bytes is not None and audio_filename:
            audio_path = self._store_audio_file(user_id=user.id, original_filename=audio_filename, payload=audio_bytes)
        item = self._entries.create(
            user_id=user.id,
            title=title.strip() or "Запись дневника",
            content=content,
            source_audio_path=audio_path,
            duration_seconds=None,
        )
        self._session.commit()
        self._session.refresh(item)
        self.process_entry_pipeline(user=user, entry_id=item.id)
        return item

    def update_entry(self, user: User, *, entry_id: str, title: str, content: str) -> DiaryEntry:
        item = self.get_entry(user, entry_id)
        item.title = title.strip() or item.title
        item.content = content
        self._entries.save(item)
        self._session.commit()
        self._session.refresh(item)
        return item

    def delete_entry(self, user: User, entry_id: str) -> None:
        item = self.get_entry(user, entry_id)
        item.is_deleted = True
        self._entries.save(item)
        self._session.commit()

    def process_entry_pipeline(self, *, user: User, entry_id: str) -> DiaryEntry:
        item = self.get_entry(user, entry_id)
        try:
            transcript = self._transcribe_entry(item)
            topics, decisions, mentions = self._extract_structure(item=item, transcript=transcript)
            item.transcript = transcript
            item.topics = topics
            item.decisions = decisions
            item.mentions = mentions
            item.processing_status = "processed"
            item.processing_error = None
            self._entries.save(item)
            self._activity.create(
                user_id=user.id,
                event_type=ActivityEventType.DIARY_ENTRY_PROCESSED,
                entity_type=ActivityEntityType.DIARY_ENTRY,
                entity_id=item.id,
                summary="Запись дневника обработана и структурирована",
                meta={"topics": len(topics), "decisions": len(decisions), "mentions": len(mentions)},
            )
            self._session.commit()
            self._session.refresh(item)
            return item
        except Exception as exc:
            item.processing_status = "failed"
            item.processing_error = str(exc)
            self._entries.save(item)
            self._session.commit()
            self._session.refresh(item)
            return item

    def _store_audio_file(self, *, user_id: str, original_filename: str, payload: bytes) -> str:
        root = Path(self._settings.diary_audio_dir).resolve()
        user_dir = root / user_id
        user_dir.mkdir(parents=True, exist_ok=True)
        suffix = Path(original_filename).suffix or ".webm"
        filename = f"{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}_{hashlib.sha1(payload).hexdigest()[:10]}{suffix}"
        out = user_dir / filename
        out.write_bytes(payload)
        return out.as_posix()

    def _transcribe_entry(self, item: DiaryEntry) -> str:
        if item.transcript.strip():
            return item.transcript
        if item.content.strip():
            return item.content
        if item.source_audio_path:
            return f"[transcript placeholder] audio={Path(item.source_audio_path).name}"
        return ""

    def _extract_structure(self, *, item: DiaryEntry, transcript: str) -> tuple[list[str], list[str], list[str]]:
        text = transcript.strip() or item.content.strip()
        if not text:
            return [], [], []
        prompt = (
            "Выдели структуру дневниковой записи. Верни JSON с полями topics, decisions, mentions, "
            "каждое поле — массив строк."
        )
        payload = {
            "model": self._settings.default_chat_model,
            "stream": False,
            "messages": [
                {"role": "system", "content": "Ты извлекаешь структуру из личного дневника."},
                {"role": "user", "content": f"{prompt}\n\nТекст:\n{text}"},
            ],
            "temperature": 0,
        }
        # best-effort: if provider unavailable, fallback to simple heuristics
        try:
            import httpx

            response = httpx.post(
                f"{self._settings.vsellm_base_url.rstrip('/')}/chat/completions",
                json=payload,
                headers={"Authorization": f"Bearer {self._settings.vsellm_api_key.strip()}"},
                timeout=httpx.Timeout(timeout=60.0, connect=10.0),
            )
            if response.status_code >= 400:
                raise RuntimeError("llm_error")
            data = response.json()
            content = ""
            choices = data.get("choices")
            if isinstance(choices, list) and choices:
                message = choices[0].get("message") if isinstance(choices[0], dict) else None
                if isinstance(message, dict) and isinstance(message.get("content"), str):
                    content = message["content"]
            parsed = json.loads(content)
            topics = [str(v) for v in parsed.get("topics", []) if isinstance(v, str)]
            decisions = [str(v) for v in parsed.get("decisions", []) if isinstance(v, str)]
            mentions = [str(v) for v in parsed.get("mentions", []) if isinstance(v, str)]
            return topics[:20], decisions[:20], mentions[:20]
        except Exception:
            words = [token.strip(".,:;!?()[]{}\"'") for token in text.split() if token.strip()]
            topics = list(dict.fromkeys([w for w in words if len(w) >= 6]))[:8]
            decisions = [line.strip() for line in text.split(".") if "решил" in line.lower() or "решили" in line.lower()][:5]
            mentions = [w for w in words if w.istitle()][:8]
            return topics, decisions, mentions
