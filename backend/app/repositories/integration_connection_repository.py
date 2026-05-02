from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.common import IntegrationConnectionStatus, IntegrationProvider
from app.db.models.integration_connection import IntegrationConnection


class IntegrationConnectionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_for_user(self, *, user_id: str) -> list[IntegrationConnection]:
        stmt = (
            select(IntegrationConnection)
            .where(IntegrationConnection.user_id == user_id)
            .order_by(IntegrationConnection.provider.asc())
        )
        return list(self._session.execute(stmt).scalars())

    def get_by_user_and_provider(self, *, user_id: str, provider: IntegrationProvider) -> IntegrationConnection | None:
        stmt = select(IntegrationConnection).where(
            IntegrationConnection.user_id == user_id,
            IntegrationConnection.provider == provider,
        )
        return self._session.execute(stmt).scalar_one_or_none()

    def upsert(
        self,
        *,
        user_id: str,
        provider: IntegrationProvider,
        status: IntegrationConnectionStatus,
        scopes: list[str],
        connected_at: Optional[datetime] = None,
        last_refresh_at: Optional[datetime] = None,
        last_sync_at: Optional[datetime] = None,
        safe_error_metadata: Optional[dict] = None,
    ) -> IntegrationConnection:
        item = self.get_by_user_and_provider(user_id=user_id, provider=provider)
        if item is None:
            item = IntegrationConnection(user_id=user_id, provider=provider)

        item.status = status
        item.scopes = scopes
        item.connected_at = connected_at
        item.last_refresh_at = last_refresh_at
        item.last_sync_at = last_sync_at
        item.safe_error_metadata = safe_error_metadata
        self._session.add(item)
        self._session.flush()
        return item
