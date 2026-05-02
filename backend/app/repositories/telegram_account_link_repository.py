from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.db.models.telegram_account_link import TelegramAccountLink


class TelegramAccountLinkRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_active_by_user_id(self, user_id: str) -> Optional[TelegramAccountLink]:
        stmt = select(TelegramAccountLink).where(
            TelegramAccountLink.user_id == user_id,
            TelegramAccountLink.is_active.is_(True),
        )
        return self._session.execute(stmt).scalar_one_or_none()

    def get_active_by_telegram_user_id(self, telegram_user_id: str) -> Optional[TelegramAccountLink]:
        stmt = select(TelegramAccountLink).where(
            TelegramAccountLink.telegram_user_id == telegram_user_id,
            TelegramAccountLink.is_active.is_(True),
        )
        return self._session.execute(stmt).scalar_one_or_none()

    def get_active_by_chat_id(self, telegram_chat_id: str) -> Optional[TelegramAccountLink]:
        stmt = select(TelegramAccountLink).where(
            TelegramAccountLink.telegram_chat_id == telegram_chat_id,
            TelegramAccountLink.is_active.is_(True),
        )
        return self._session.execute(stmt).scalar_one_or_none()

    def create(
        self,
        *,
        user_id: str,
        telegram_user_id: str,
        telegram_chat_id: str,
        telegram_username: str | None,
        linked_at: datetime,
    ) -> TelegramAccountLink:
        link = TelegramAccountLink(
            user_id=user_id,
            telegram_user_id=telegram_user_id,
            telegram_chat_id=telegram_chat_id,
            telegram_username=telegram_username,
            linked_at=linked_at,
            is_active=True,
        )
        self._session.add(link)
        self._session.flush()
        return link

    def deactivate(self, link: TelegramAccountLink, *, at: datetime) -> TelegramAccountLink:
        link.is_active = False
        link.unlinked_at = at
        self._session.add(link)
        self._session.flush()
        return link

    def list_active(self, *, limit: int = 1000) -> list[TelegramAccountLink]:
        stmt = (
            select(TelegramAccountLink)
            .where(TelegramAccountLink.is_active.is_(True))
            .order_by(desc(TelegramAccountLink.linked_at))
            .limit(limit)
        )
        return list(self._session.execute(stmt).scalars())
