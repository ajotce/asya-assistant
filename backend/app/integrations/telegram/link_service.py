from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models.common import IntegrationConnectionStatus, IntegrationProvider
from app.db.models.telegram_account_link import TelegramAccountLink
from app.db.models.user import User
from app.repositories.telegram_account_link_repository import TelegramAccountLinkRepository
from app.repositories.telegram_link_token_repository import TelegramLinkTokenRepository
from app.services.integration_connection_service import IntegrationConnectionService, IntegrationConnectionUpsertPayload


class TelegramLinkError(ValueError):
    pass


@dataclass
class TelegramLinkStatus:
    is_linked: bool
    telegram_user_id: str | None
    telegram_username: str | None
    telegram_chat_id: str | None


@dataclass
class TelegramLinkTokenResult:
    one_time_token: str
    expires_at: datetime
    bot_start_url: str


class TelegramLinkService:
    def __init__(self, session: Session, settings: Settings) -> None:
        self._session = session
        self._settings = settings
        self._links = TelegramAccountLinkRepository(session)
        self._tokens = TelegramLinkTokenRepository(session)
        self._integrations = IntegrationConnectionService(session)

    def status(self, *, user: User) -> TelegramLinkStatus:
        link = self._links.get_active_by_user_id(user.id)
        if link is None:
            return TelegramLinkStatus(False, None, None, None)
        return TelegramLinkStatus(
            is_linked=True,
            telegram_user_id=link.telegram_user_id,
            telegram_username=link.telegram_username,
            telegram_chat_id=link.telegram_chat_id,
        )

    def create_one_time_token(self, *, user: User) -> TelegramLinkTokenResult:
        raw_token = secrets.token_urlsafe(32)
        hashed = self._hash(raw_token)
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=self._settings.telegram_link_token_ttl_seconds)
        self._tokens.delete_active_for_user(user.id)
        self._tokens.create(user_id=user.id, token_hash=hashed, expires_at=expires_at)
        self._session.flush()
        bot_username = self._settings.telegram_bot_username.strip().lstrip("@")
        if not bot_username:
            raise TelegramLinkError("TELEGRAM_BOT_USERNAME не настроен.")
        return TelegramLinkTokenResult(
            one_time_token=raw_token,
            expires_at=expires_at,
            bot_start_url=f"https://t.me/{bot_username}?start={raw_token}",
        )

    def unlink(self, *, user: User) -> bool:
        link = self._links.get_active_by_user_id(user.id)
        if link is None:
            self._tokens.delete_active_for_user(user.id)
            self._integrations.disconnect(user=user, provider=IntegrationProvider.TELEGRAM)
            self._session.flush()
            return False
        self._links.deactivate(link, at=datetime.now(timezone.utc))
        self._tokens.delete_active_for_user(user.id)
        self._integrations.disconnect(user=user, provider=IntegrationProvider.TELEGRAM)
        self._session.flush()
        return True

    def consume_start_token(
        self,
        *,
        token: str,
        telegram_user_id: str,
        telegram_chat_id: str,
        telegram_username: str | None,
    ) -> TelegramAccountLink:
        token_hash = self._hash(token)
        token_row = self._tokens.get_valid_by_hash(token_hash)
        if token_row is None:
            raise TelegramLinkError("Токен привязки недействителен или истек.")

        existing_for_user = self._links.get_active_by_user_id(token_row.user_id)
        if existing_for_user is not None:
            self._links.deactivate(existing_for_user, at=datetime.now(timezone.utc))

        existing_tg = self._links.get_active_by_telegram_user_id(telegram_user_id)
        if existing_tg is not None and existing_tg.user_id != token_row.user_id:
            self._links.deactivate(existing_tg, at=datetime.now(timezone.utc))

        self._tokens.mark_used(token_row, telegram_user_id=telegram_user_id, used_at=datetime.now(timezone.utc))
        link = self._links.create(
            user_id=token_row.user_id,
            telegram_user_id=telegram_user_id,
            telegram_chat_id=telegram_chat_id,
            telegram_username=telegram_username,
            linked_at=datetime.now(timezone.utc),
        )
        self._integrations.upsert_connection_by_user_id(
            user_id=token_row.user_id,
            payload=IntegrationConnectionUpsertPayload(
                provider=IntegrationProvider.TELEGRAM,
                status=IntegrationConnectionStatus.CONNECTED,
                scopes=["bot:messages", "bot:voice"],
                connected_at=link.linked_at,
            ),
        )
        self._session.flush()
        return link

    @staticmethod
    def _hash(raw: str) -> str:
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()
