from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models.common import IntegrationConnectionStatus, IntegrationProvider
from app.db.models.integration_connection import IntegrationConnection
from app.db.models.user import User
from app.repositories.integration_connection_repository import IntegrationConnectionRepository
from app.services.encrypted_secret_service import EncryptedSecretService
from app.services.secret_crypto_service import SecretCryptoService
from app.repositories.activity_log_repository import ActivityLogRepository
from app.db.models.common import ActivityEntityType, ActivityEventType


class IntegrationConnectionNotFoundError(ValueError):
    pass


class IntegrationValidationError(ValueError):
    pass


@dataclass
class IntegrationConnectionUpsertPayload:
    provider: IntegrationProvider
    status: IntegrationConnectionStatus
    scopes: list[str]
    connected_at: Optional[datetime] = None
    last_refresh_at: Optional[datetime] = None
    last_sync_at: Optional[datetime] = None
    safe_error_metadata: Optional[dict] = None
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None


class IntegrationConnectionService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._repo = IntegrationConnectionRepository(session)
        self._activity = ActivityLogRepository(session)
        self._secret_service = EncryptedSecretService(
            session,
            SecretCryptoService(get_settings().master_encryption_key),
        )

    def list_connections(self, *, user: User) -> list[IntegrationConnection]:
        return self._repo.list_for_user(user_id=user.id)

    def list_connections_by_user_id(self, *, user_id: str) -> list[IntegrationConnection]:
        return self._repo.list_for_user(user_id=user_id)

    def get_connection(self, *, user: User, provider: IntegrationProvider) -> IntegrationConnection:
        item = self._repo.get_by_user_and_provider(user_id=user.id, provider=provider)
        if item is None:
            raise IntegrationConnectionNotFoundError("Подключение не найдено.")
        return item

    def get_connection_by_user_id(self, *, user_id: str, provider: IntegrationProvider) -> IntegrationConnection:
        item = self._repo.get_by_user_and_provider(user_id=user_id, provider=provider)
        if item is None:
            raise IntegrationConnectionNotFoundError("Подключение не найдено.")
        return item

    def get_connection_or_default(self, *, user: User, provider: IntegrationProvider) -> IntegrationConnection:
        item = self._repo.get_by_user_and_provider(user_id=user.id, provider=provider)
        if item is not None:
            return item
        return IntegrationConnection(
            user_id=user.id,
            provider=provider,
            status=IntegrationConnectionStatus.NOT_CONNECTED,
            scopes=[],
        )

    def upsert_connection(self, *, user: User, payload: IntegrationConnectionUpsertPayload) -> IntegrationConnection:
        return self.upsert_connection_by_user_id(user_id=user.id, payload=payload)

    def upsert_connection_by_user_id(self, *, user_id: str, payload: IntegrationConnectionUpsertPayload) -> IntegrationConnection:
        scopes = self._normalize_scopes(payload.scopes)
        item = self._repo.upsert(
            user_id=user_id,
            provider=payload.provider,
            status=payload.status,
            scopes=scopes,
            connected_at=payload.connected_at,
            last_refresh_at=payload.last_refresh_at,
            last_sync_at=payload.last_sync_at,
            safe_error_metadata=payload.safe_error_metadata,
        )
        self._session.commit()

        if payload.access_token:
            self._secret_service.set_secret(
                user_id=user_id,
                secret_type="integration_access_token",
                name=self._secret_name(payload.provider, "access_token"),
                plaintext_value=payload.access_token,
            )
        if payload.refresh_token:
            self._secret_service.set_secret(
                user_id=user_id,
                secret_type="integration_refresh_token",
                name=self._secret_name(payload.provider, "refresh_token"),
                plaintext_value=payload.refresh_token,
            )
        self._activity.create(
            user_id=user_id,
            event_type=ActivityEventType.INTEGRATION_ACTION_EXECUTED,
            entity_type=ActivityEntityType.INTEGRATION_ACTION,
            entity_id=item.id,
            summary=f"Integration updated: {payload.provider.value}",
            meta={
                "provider": payload.provider.value,
                "status": payload.status.value,
                "scope_count": len(scopes),
                "has_access_token": bool(payload.access_token),
                "has_refresh_token": bool(payload.refresh_token),
            },
        )
        self._session.commit()
        return item

    def mark_status(
        self,
        *,
        user: User,
        provider: IntegrationProvider,
        status: IntegrationConnectionStatus,
        safe_error_metadata: Optional[dict] = None,
    ) -> IntegrationConnection:
        item = self.get_connection(user=user, provider=provider)
        if status == IntegrationConnectionStatus.ERROR and safe_error_metadata is None:
            raise IntegrationValidationError("Для статуса error требуется safe error metadata.")
        item.status = status
        item.safe_error_metadata = safe_error_metadata
        if status == IntegrationConnectionStatus.CONNECTED and item.connected_at is None:
            item.connected_at = self._now()
        self._session.add(item)
        self._session.commit()
        self._activity.create(
            user_id=user.id,
            event_type=ActivityEventType.INTEGRATION_ACTION_EXECUTED,
            entity_type=ActivityEntityType.INTEGRATION_ACTION,
            entity_id=item.id,
            summary=f"Integration disconnected: {provider.value}",
            meta={"provider": provider.value, "status": item.status.value},
        )
        self._session.commit()
        return item

    def mark_refreshed(self, *, user: User, provider: IntegrationProvider, at: Optional[datetime] = None) -> IntegrationConnection:
        item = self.get_connection(user=user, provider=provider)
        item.last_refresh_at = at or self._now()
        self._session.add(item)
        self._session.commit()
        return item

    def mark_synced(self, *, user: User, provider: IntegrationProvider, at: Optional[datetime] = None) -> IntegrationConnection:
        item = self.get_connection(user=user, provider=provider)
        item.last_sync_at = at or self._now()
        self._session.add(item)
        self._session.commit()
        return item

    def mark_synced_by_user_id(
        self,
        *,
        user_id: str,
        provider: IntegrationProvider,
        at: Optional[datetime] = None,
    ) -> IntegrationConnection:
        item = self.get_connection_by_user_id(user_id=user_id, provider=provider)
        item.last_sync_at = at or self._now()
        self._session.add(item)
        self._session.commit()
        return item

    def disconnect(self, *, user: User, provider: IntegrationProvider) -> IntegrationConnection:
        item = self._repo.get_by_user_and_provider(user_id=user.id, provider=provider)
        if item is None:
            item = self._repo.upsert(
                user_id=user.id,
                provider=provider,
                status=IntegrationConnectionStatus.NOT_CONNECTED,
                scopes=[],
                connected_at=None,
                last_refresh_at=None,
                last_sync_at=None,
                safe_error_metadata=None,
            )
        else:
            item.status = IntegrationConnectionStatus.REVOKED
            item.safe_error_metadata = None
            item.last_refresh_at = None
            self._session.add(item)
        self._session.commit()

        self._secret_service.delete_secret(
            user_id=user.id,
            name=self._secret_name(provider, "access_token"),
        )
        self._secret_service.delete_secret(
            user_id=user.id,
            name=self._secret_name(provider, "refresh_token"),
        )
        return item

    @staticmethod
    def _secret_name(provider: IntegrationProvider, token_type: str) -> str:
        return f"integration:{provider.value}:{token_type}"

    @staticmethod
    def _normalize_scopes(scopes: list[str]) -> list[str]:
        normalized: list[str] = []
        for raw in scopes:
            scope = raw.strip()
            if scope and scope not in normalized:
                normalized.append(scope)
        return normalized

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)
