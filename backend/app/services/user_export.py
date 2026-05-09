from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
from pathlib import Path
import secrets
import threading
from typing import Any
import zipfile

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models.activity_log import ActivityLog
from app.db.models.assistant_personality_profile import AssistantPersonalityProfile
from app.db.models.auth_session import AuthSession
from app.db.models.behavior_rule import BehaviorRule
from app.db.models.chat import Chat
from app.db.models.common import UserExportStatus
from app.db.models.deleted_user_audit import DeletedUserAudit
from app.db.models.diary_entry import DiaryEntry
from app.db.models.diary_settings import DiarySettings
from app.db.models.encrypted_secret import EncryptedSecret
from app.db.models.file_meta import FileMeta
from app.db.models.integration_connection import IntegrationConnection
from app.db.models.memory_change import MemoryChange
from app.db.models.memory_chunk import MemoryChunk
from app.db.models.memory_episode import MemoryEpisode
from app.db.models.memory_snapshot import MemorySnapshot
from app.db.models.message import Message
from app.db.models.oauth_state import OAuthState
from app.db.models.observation import Observation
from app.db.models.observation_rule import ObservationRule
from app.db.models.pending_action import PendingAction
from app.db.models.signup_token import SignupToken
from app.db.models.space import Space
from app.db.models.space_memory_settings import SpaceMemorySettings
from app.db.models.telegram_account_link import TelegramAccountLink
from app.db.models.telegram_link_token import TelegramLinkToken
from app.db.models.user import User
from app.db.models.user_export import UserExport
from app.db.models.user_profile_fact import UserProfileFact
from app.db.models.user_settings import UserSettings
from app.db.models.user_voice_settings import UserVoiceSettings
from app.db.models.usage_record import UsageRecord
from app.db.session import create_session
from app.services.auth_service import AuthService


class UserExportError(ValueError):
    pass


class UserExportService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._settings = get_settings()

    def start_export(self, user_id: str) -> str:
        export_id = self._create_export_record(user_id)
        threading.Thread(target=self._run_export_background, args=(export_id,), daemon=True).start()
        return export_id

    def _create_export_record(self, user_id: str) -> str:
        export = UserExport(user_id=user_id)
        self._session.add(export)
        self._session.flush()
        export_id = export.id
        self._session.commit()
        return export_id

    @staticmethod
    def _run_export_background(export_id: str) -> None:
        session = create_session()
        try:
            service = UserExportService(session)
            service.run_export(export_id)
        finally:
            session.close()

    def run_export(self, export_id: str) -> None:
        export = self._session.get(UserExport, export_id)
        if export is None:
            return
        user = self._session.get(User, export.user_id)
        if user is None:
            export.status = UserExportStatus.FAILED
            self._session.commit()
            return

        export.status = UserExportStatus.PROCESSING
        self._session.commit()

        export_dir = Path(self._settings.export_dir).resolve()
        export_dir.mkdir(parents=True, exist_ok=True)
        zip_path = export_dir / f"user-export-{export.user_id}-{export.id}.zip"

        try:
            with zipfile.ZipFile(zip_path, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
                self._write_json(archive, "profile.json", self._row_to_dict(user))
                self._write_json(archive, "chats.json", self._rows(Chat, export.user_id))
                self._write_json(archive, "messages.json", self._rows(Message, export.user_id, by_chat=True))
                self._write_json(archive, "episodes.json", self._rows(MemoryEpisode, export.user_id))
                self._write_json(archive, "rules.json", self._rows(BehaviorRule, export.user_id))
                self._write_json(
                    archive,
                    "personality_versions.json",
                    self._rows(AssistantPersonalityProfile, export.user_id),
                )
                self._write_json(archive, "diary_entries.json", self._rows(DiaryEntry, export.user_id))
                self._write_json(archive, "activity.json", self._rows(ActivityLog, export.user_id))
                self._write_json(archive, "observations.json", self._rows(Observation, export.user_id))
                self._write_json(archive, "templates.json", self._rows(FileMeta, export.user_id))
                self._write_json(archive, "facts.json", self._rows(UserProfileFact, export.user_id))
                self._write_json(archive, "spaces.json", self._rows(Space, export.user_id))
                self._write_json(archive, "space_settings.json", self._rows(SpaceMemorySettings, export.user_id))
                self._write_json(archive, "diary_settings.json", self._rows(DiarySettings, export.user_id))
                self._write_diary_audio(archive, export.user_id)

            export.status = UserExportStatus.READY
            export.file_path = str(zip_path)
            export.download_token = None
            export.expires_at = None
            self._session.commit()
        except Exception:
            export.status = UserExportStatus.FAILED
            export.file_path = None
            export.download_token = None
            export.expires_at = None
            self._session.commit()
            raise

    def get_download_url(self, export_id: str, user_id: str) -> tuple[str, datetime]:
        export = self._owned_export(export_id=export_id, user_id=user_id)
        if export.status.value != "ready":
            raise UserExportError("Экспорт ещё не готов.")
        token = secrets.token_urlsafe(48)
        token_hash = self._hash_token(token)
        expires_at = self._now() + timedelta(hours=24)
        export.download_token = token_hash
        export.expires_at = expires_at
        self._session.commit()
        return token, expires_at

    def get_status(self, export_id: str, user_id: str) -> UserExport:
        return self._owned_export(export_id=export_id, user_id=user_id)

    def consume_download_token(self, token: str) -> str:
        token_hash = self._hash_token(token)
        stmt = select(UserExport).where(UserExport.download_token == token_hash)
        export = self._session.execute(stmt).scalar_one_or_none()
        if export is None or export.status.value != "ready" or export.expires_at is None:
            raise UserExportError("Ссылка недействительна.")
        if self._to_utc(export.expires_at) <= self._now():
            raise UserExportError("Ссылка истекла.")
        if not export.file_path:
            raise UserExportError("Файл экспорта не найден.")

        export.download_token = None
        export.expires_at = None
        self._session.commit()
        return export.file_path

    def prepare_delete_confirmation(self, user: User, password: str) -> tuple[str, datetime]:
        if user.password_hash is None or not AuthService._verify_password(password, user.password_hash):
            raise UserExportError("Неверный пароль.")
        expires_at = self._now() + timedelta(minutes=5)
        payload = f"{user.id}:{int(expires_at.timestamp())}:{secrets.token_urlsafe(12)}"
        signature = hmac.new(
            self._settings.auth_session_hash_secret.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        token = f"{payload}.{signature}"
        return token, expires_at

    def delete_user(self, current_user: User, confirmation_token: str) -> tuple[str, str | None, datetime | None]:
        self._validate_confirmation_token(current_user.id, confirmation_token)

        export_id = self._create_export_record(current_user.id)
        self.run_export(export_id)

        token: str | None = None
        expires_at: datetime | None = None
        export = self._session.get(UserExport, export_id)
        if export is not None and export.status.value == "ready":
            token, expires_at = self.get_download_url(export_id, current_user.id)

        had_export = export is not None and export.status.value == "ready"
        self._session.add(
            DeletedUserAudit(
                user_id=current_user.id,
                email=current_user.email,
                deleted_at=self._now(),
                had_export=had_export,
            )
        )

        self._cleanup_user_data(current_user.id)
        self._session.delete(current_user)
        self._session.commit()
        return export_id, token, expires_at

    def _cleanup_user_data(self, user_id: str) -> None:
        chat_ids = [row[0] for row in self._session.execute(select(Chat.id).where(Chat.user_id == user_id)).all()]
        audio_paths = self._session.execute(select(DiaryEntry.source_audio_path).where(DiaryEntry.user_id == user_id)).all()

        if chat_ids:
            self._session.execute(delete(Message).where(Message.chat_id.in_(chat_ids)))
            self._session.execute(delete(PendingAction).where(PendingAction.session_id.in_(chat_ids)))

        for model in (
            ActivityLog,
            AssistantPersonalityProfile,
            AuthSession,
            BehaviorRule,
            Chat,
            DiaryEntry,
            DiarySettings,
            EncryptedSecret,
            FileMeta,
            IntegrationConnection,
            MemoryChange,
            MemoryChunk,
            MemoryEpisode,
            MemorySnapshot,
            OAuthState,
            Observation,
            ObservationRule,
            PendingAction,
            SpaceMemorySettings,
            Space,
            TelegramAccountLink,
            TelegramLinkToken,
            UserProfileFact,
            UserSettings,
            UserVoiceSettings,
            UsageRecord,
            SignupToken,
        ):
            self._session.execute(delete(model).where(model.user_id == user_id))

        exports = self._session.execute(select(UserExport).where(UserExport.user_id == user_id)).scalars().all()
        for export in exports:
            if export.file_path:
                self._safe_remove_file(Path(export.file_path))
        self._session.execute(delete(UserExport).where(UserExport.user_id == user_id))

        for (audio_path,) in audio_paths:
            if audio_path:
                self._safe_remove_file(Path(audio_path))

    def _safe_remove_file(self, path: Path) -> None:
        resolved = path.resolve()
        export_root = Path(self._settings.export_dir).resolve()
        diary_root = Path(self._settings.diary_audio_dir).resolve()
        if str(resolved).startswith(str(export_root)) or str(resolved).startswith(str(diary_root)):
            if resolved.exists() and resolved.is_file():
                resolved.unlink(missing_ok=True)

    def _rows(self, model: Any, user_id: str, *, by_chat: bool = False) -> list[dict[str, Any]]:
        if by_chat:
            chat_ids = select(Chat.id).where(Chat.user_id == user_id)
            rows = self._session.execute(select(model).where(model.chat_id.in_(chat_ids))).scalars().all()
        else:
            rows = self._session.execute(select(model).where(model.user_id == user_id)).scalars().all()
        return [self._row_to_dict(row) for row in rows]

    def _write_diary_audio(self, archive: zipfile.ZipFile, user_id: str) -> None:
        entries = self._session.execute(select(DiaryEntry).where(DiaryEntry.user_id == user_id)).scalars().all()
        for entry in entries:
            if not entry.source_audio_path:
                continue
            path = Path(entry.source_audio_path)
            if path.exists() and path.is_file():
                archive.write(path, arcname=f"diary_audio/{path.name}")

    def _write_json(self, archive: zipfile.ZipFile, arcname: str, payload: Any) -> None:
        archive.writestr(arcname, json.dumps(payload, ensure_ascii=False, indent=2))

    def _row_to_dict(self, row: Any) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for column in row.__table__.columns:
            value = getattr(row, column.key)
            if isinstance(value, datetime):
                result[column.name] = value.isoformat()
            elif isinstance(value, bytes):
                result[column.name] = None
            elif hasattr(value, "value"):
                result[column.name] = value.value
            else:
                try:
                    json.dumps(value)
                    result[column.name] = value
                except TypeError:
                    result[column.name] = str(value)
        return result

    def _owned_export(self, export_id: str, user_id: str) -> UserExport:
        export = self._session.get(UserExport, export_id)
        if export is None or export.user_id != user_id:
            raise UserExportError("Экспорт не найден.")
        return export

    def _validate_confirmation_token(self, user_id: str, token: str) -> None:
        try:
            payload, signature = token.rsplit(".", maxsplit=1)
            expected = hmac.new(
                self._settings.auth_session_hash_secret.encode("utf-8"),
                payload.encode("utf-8"),
                hashlib.sha256,
            ).hexdigest()
            if not hmac.compare_digest(signature, expected):
                raise ValueError
            token_user_id, exp_raw, _nonce = payload.split(":", maxsplit=2)
            exp = datetime.fromtimestamp(int(exp_raw), tz=timezone.utc)
        except Exception as exc:
            raise UserExportError("Некорректный confirmation token.") from exc

        if token_user_id != user_id:
            raise UserExportError("Некорректный confirmation token.")
        if exp <= self._now():
            raise UserExportError("Confirmation token истёк.")

    def _hash_token(self, raw_token: str) -> str:
        key = self._settings.auth_session_hash_secret.encode("utf-8")
        return hmac.new(key=key, msg=raw_token.encode("utf-8"), digestmod=hashlib.sha256).hexdigest()

    @staticmethod
    def _now() -> datetime:
        return datetime.now(tz=timezone.utc)

    @staticmethod
    def _to_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
