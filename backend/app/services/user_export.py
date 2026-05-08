from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import io
import json
import secrets
import zipfile

from sqlalchemy import delete, inspect, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models.access_request import AccessRequest
from app.db.models.activity_log import ActivityLog
from app.db.models.assistant_personality_profile import AssistantPersonalityProfile
from app.db.models.auth_session import AuthSession
from app.db.models.behavior_rule import BehaviorRule
from app.db.models.chat import Chat
from app.db.models.common import UserStatus
from app.db.models.deleted_user_audit import DeletedUserAudit
from app.db.models.diary_entry import DiaryEntry
from app.db.models.encrypted_secret import EncryptedSecret
from app.db.models.file_meta import FileMeta
from app.db.models.integration_connection import IntegrationConnection
from app.db.models.memory_episode import MemoryEpisode
from app.db.models.message import Message
from app.db.models.observation import Observation
from app.db.models.observation_rule import ObservationRule
from app.db.models.space import Space
from app.db.models.user import User
from app.db.models.user_export import UserExport
from app.db.models.user_profile_fact import UserProfileFact
from app.storage.runtime import blob_storage


@dataclass
class ExportStatus:
    export_id: str
    status: str
    download_url: str | None
    expires_at: str | None
    error: str | None


class UserExportService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._settings = get_settings()

    def start_export(self, user_id: str) -> str:
        export = UserExport(user_id=user_id, status="pending")
        self._session.add(export)
        self._session.commit()
        return export.id

    def run_export(self, export_id: str) -> None:
        export = self._session.get(UserExport, export_id)
        if export is None:
            return
        export.status = "processing"
        export.started_at = self._now()
        export.error = None
        self._session.commit()

        try:
            payload = self._build_payload(export.user_id)
            archive_bytes = self._build_zip(payload=payload, user_id=export.user_id)
            object_key = f"exports/{export.user_id}/{export.id}.zip"
            blob_storage.put_bytes(object_key, archive_bytes)

            export.object_key = object_key
            export.expires_at = self._now() + timedelta(hours=24)
            export.download_token = None
            if self._settings.object_storage_backend.strip().lower() == "s3":
                export.download_url = blob_storage.presigned_url(object_key, expires_in_seconds=86_400)
            else:
                # Backward-compatible local fallback for dev mode.
                export.download_token = secrets.token_urlsafe(48)
                export.download_url = (
                    f"{self._settings.public_base_url.rstrip('/')}/api/me/export/{export.id}/download"
                    f"?token={export.download_token}"
                )
            export.status = "ready"
            export.finished_at = self._now()
            self._session.commit()
        except Exception as exc:
            export.status = "failed"
            export.error = str(exc)
            export.finished_at = self._now()
            self._session.commit()

    def get_status(self, user_id: str, export_id: str) -> ExportStatus:
        export = self._session.get(UserExport, export_id)
        if export is None or export.user_id != user_id:
            raise ValueError("Экспорт не найден.")
        return ExportStatus(
            export_id=export.id,
            status=export.status,
            download_url=export.download_url if export.status == "ready" else None,
            expires_at=export.expires_at.isoformat() if export.expires_at else None,
            error=export.error,
        )

    def delete_export(self, user_id: str, export_id: str) -> None:
        export = self._session.get(UserExport, export_id)
        if export is None or export.user_id != user_id:
            raise ValueError("Экспорт не найден.")
        if export.object_key:
            blob_storage.delete(export.object_key)
        self._session.delete(export)
        self._session.commit()

    def consume_download(self, user_id: str, export_id: str, token: str) -> tuple[str, bytes]:
        export = self._session.get(UserExport, export_id)
        if export is None or export.user_id != user_id:
            raise ValueError("Экспорт не найден.")
        if export.status != "ready" or not export.object_key:
            raise ValueError("Экспорт ещё не готов.")
        expires_at = self._as_utc(export.expires_at)
        if expires_at is None or expires_at < self._now():
            raise ValueError("Срок действия ссылки истёк.")
        if not export.download_token or not hmac.compare_digest(export.download_token, token):
            raise ValueError("Неверный token скачивания.")
        payload = blob_storage.get_bytes(export.object_key)
        export.download_token = None
        export.download_url = None
        self._session.commit()
        return f"user-export-{export.id}.zip", payload

    def create_delete_confirmation_token(self, user_id: str) -> str:
        expires_at = int((self._now() + timedelta(minutes=15)).timestamp())
        nonce = secrets.token_urlsafe(16)
        payload = f"{user_id}:{expires_at}:{nonce}"
        signature = hmac.new(
            self._settings.auth_session_hash_secret.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return f"{payload}:{signature}"

    def verify_delete_confirmation_token(self, user_id: str, token: str) -> bool:
        try:
            payload_user_id, expires_at_raw, nonce, signature = token.split(":", 3)
        except ValueError:
            return False
        if payload_user_id != user_id:
            return False
        payload = f"{payload_user_id}:{expires_at_raw}:{nonce}"
        expected = hmac.new(
            self._settings.auth_session_hash_secret.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(signature, expected):
            return False
        return int(expires_at_raw) >= int(self._now().timestamp())

    def delete_account(self, user: User, password: str, confirmation_token: str) -> ExportStatus:
        from app.services.auth_service import AuthService

        if not self.verify_delete_confirmation_token(user.id, confirmation_token):
            raise ValueError("Некорректный confirmation_token.")
        if user.password_hash is None or not AuthService._verify_password(password, user.password_hash):  # noqa: SLF001
            raise ValueError("Неверный пароль.")

        export_id = self.start_export(user.id)
        self.run_export(export_id)
        status = self.get_status(user.id, export_id)

        object_keys = self._collect_object_keys(user.id)
        for key in object_keys:
            blob_storage.delete(key)

        user_id = user.id
        self._delete_user_rows(user_id)
        self._session.add(
            DeletedUserAudit(
                deleted_user_id=user_id,
                initiated_by_user_id=user_id,
                deleted_at=self._now(),
                export_id=export_id,
            )
        )
        self._session.execute(delete(User).where(User.id == user_id))
        self._session.commit()
        return status

    def _build_payload(self, user_id: str) -> dict[str, object]:
        user = self._session.get(User, user_id)
        if user is None or user.status == UserStatus.DISABLED:
            raise ValueError("Пользователь не найден.")
        data: dict[str, object] = {
            "profile": self._serialize_row(user, exclude={"password_hash"}),
            "chats": self._serialize_query(select(Chat).where(Chat.user_id == user_id)),
            "messages": self._serialize_query(select(Message).where(Message.user_id == user_id)),
            "episodes": self._serialize_query(select(MemoryEpisode).where(MemoryEpisode.user_id == user_id)),
            "rules": self._serialize_query(select(BehaviorRule).where(BehaviorRule.user_id == user_id)),
            "personality_versions": self._serialize_query(
                select(AssistantPersonalityProfile).where(AssistantPersonalityProfile.user_id == user_id)
            ),
            "diary": self._serialize_query(select(DiaryEntry).where(DiaryEntry.user_id == user_id)),
            "activity": self._serialize_query(select(ActivityLog).where(ActivityLog.user_id == user_id)),
            "observations": self._serialize_query(select(Observation).where(Observation.user_id == user_id)),
            "observation_rules": self._serialize_query(
                select(ObservationRule).where(ObservationRule.user_id == user_id)
            ),
            "templates": self._serialize_query(select(FileMeta).where(FileMeta.user_id == user_id)),
            "facts": self._serialize_query(select(UserProfileFact).where(UserProfileFact.user_id == user_id)),
            "spaces": self._serialize_query(select(Space).where(Space.user_id == user_id)),
            "integrations": self._serialize_query(
                select(IntegrationConnection).where(IntegrationConnection.user_id == user_id)
            ),
            "access_requests": self._serialize_query(select(AccessRequest).where(AccessRequest.email == user.email)),
        }
        self._assert_no_integration_tokens(data)
        return data

    def _build_zip(self, *, payload: dict[str, object], user_id: str) -> bytes:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("export.json", json.dumps(payload, ensure_ascii=False, indent=2, default=str))
            entries = self._session.execute(
                select(DiaryEntry).where(DiaryEntry.user_id == user_id, DiaryEntry.source_audio_path.is_not(None))
            ).scalars()
            for entry in entries:
                if not entry.source_audio_path:
                    continue
                try:
                    audio = blob_storage.get_bytes(entry.source_audio_path)
                except Exception:
                    continue
                filename = entry.source_audio_path.split("/")[-1]
                archive.writestr(f"diary_audio/{entry.id}_{filename}", audio)
        return buffer.getvalue()

    def _assert_no_integration_tokens(self, data: dict[str, object]) -> None:
        serialized = json.dumps(data, ensure_ascii=False, default=str).lower()
        forbidden = ("access_token", "refresh_token", "token", "encrypted_secrets", "authorization")
        if any(secret in serialized for secret in forbidden):
            raise ValueError("Экспорт содержит запрещённые секреты.")
        has_secrets = self._session.execute(
            select(EncryptedSecret.id).where(EncryptedSecret.user_id == data["profile"]["id"])  # type: ignore[index]
        ).first()
        if has_secrets and "integrations" in data:
            # Интеграции допускаются только как metadata без токенов.
            return

    def _serialize_query(self, stmt) -> list[dict[str, object]]:
        rows = self._session.execute(stmt).scalars().all()
        return [self._serialize_row(row) for row in rows]

    def _serialize_row(self, row: object, *, exclude: set[str] | None = None) -> dict[str, object]:
        exclude = exclude or set()
        inspected = inspect(row)
        mapper = getattr(inspected, "mapper", None)
        if mapper is None:
            return {}
        result: dict[str, object] = {}
        for column in mapper.columns:
            name = column.key
            if name in exclude:
                continue
            value = getattr(row, name)
            if isinstance(value, datetime):
                result[name] = value.isoformat()
            else:
                result[name] = value
        return result

    def _collect_object_keys(self, user_id: str) -> set[str]:
        keys: set[str] = set()
        for file_meta in self._session.execute(select(FileMeta).where(FileMeta.user_id == user_id)).scalars():
            keys.add(file_meta.storage_path)
        for diary in self._session.execute(select(DiaryEntry).where(DiaryEntry.user_id == user_id)).scalars():
            if diary.source_audio_path:
                keys.add(diary.source_audio_path)
        for export in self._session.execute(select(UserExport).where(UserExport.user_id == user_id)).scalars():
            if export.object_key:
                keys.add(export.object_key)
        return keys

    def _delete_user_rows(self, user_id: str) -> None:
        self._session.execute(delete(AuthSession).where(AuthSession.user_id == user_id))
        self._session.execute(delete(EncryptedSecret).where(EncryptedSecret.user_id == user_id))
        self._session.execute(delete(UserExport).where(UserExport.user_id == user_id))
        self._session.execute(delete(Message).where(Message.user_id == user_id))
        self._session.execute(delete(Chat).where(Chat.user_id == user_id))
        self._session.execute(delete(FileMeta).where(FileMeta.user_id == user_id))
        self._session.execute(delete(DiaryEntry).where(DiaryEntry.user_id == user_id))
        self._session.execute(delete(ActivityLog).where(ActivityLog.user_id == user_id))
        self._session.execute(delete(Observation).where(Observation.user_id == user_id))
        self._session.execute(delete(ObservationRule).where(ObservationRule.user_id == user_id))
        self._session.execute(delete(BehaviorRule).where(BehaviorRule.user_id == user_id))
        self._session.execute(delete(MemoryEpisode).where(MemoryEpisode.user_id == user_id))
        self._session.execute(delete(UserProfileFact).where(UserProfileFact.user_id == user_id))
        self._session.execute(delete(Space).where(Space.user_id == user_id))
        self._session.execute(delete(IntegrationConnection).where(IntegrationConnection.user_id == user_id))

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _as_utc(value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
