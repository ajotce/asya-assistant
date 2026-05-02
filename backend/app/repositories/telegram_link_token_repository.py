from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import and_, delete, select
from sqlalchemy.orm import Session

from app.db.models.telegram_link_token import TelegramLinkToken


class TelegramLinkTokenRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, *, user_id: str, token_hash: str, expires_at: datetime) -> TelegramLinkToken:
        token = TelegramLinkToken(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
        self._session.add(token)
        self._session.flush()
        return token

    def get_valid_by_hash(self, token_hash: str) -> Optional[TelegramLinkToken]:
        now = datetime.now(timezone.utc)
        stmt = select(TelegramLinkToken).where(
            TelegramLinkToken.token_hash == token_hash,
            TelegramLinkToken.used_at.is_(None),
            TelegramLinkToken.expires_at > now,
        )
        return self._session.execute(stmt).scalar_one_or_none()

    def get_active_for_user(self, user_id: str) -> list[TelegramLinkToken]:
        now = datetime.now(timezone.utc)
        stmt = select(TelegramLinkToken).where(
            TelegramLinkToken.user_id == user_id,
            TelegramLinkToken.used_at.is_(None),
            TelegramLinkToken.expires_at > now,
        )
        return list(self._session.execute(stmt).scalars())

    def mark_used(
        self,
        token: TelegramLinkToken,
        *,
        telegram_user_id: str,
        used_at: datetime,
    ) -> TelegramLinkToken:
        token.used_at = used_at
        token.consumed_by_telegram_user_id = telegram_user_id
        self._session.add(token)
        self._session.flush()
        return token

    def delete_active_for_user(self, user_id: str) -> int:
        now = datetime.now(timezone.utc)
        stmt = delete(TelegramLinkToken).where(
            and_(
                TelegramLinkToken.user_id == user_id,
                TelegramLinkToken.used_at.is_(None),
                TelegramLinkToken.expires_at > now,
            )
        )
        result = self._session.execute(stmt)
        return int(result.rowcount or 0)

    def prune_expired(self) -> int:
        now = datetime.now(timezone.utc)
        stmt = delete(TelegramLinkToken).where(TelegramLinkToken.expires_at <= now)
        result = self._session.execute(stmt)
        return int(result.rowcount or 0)
