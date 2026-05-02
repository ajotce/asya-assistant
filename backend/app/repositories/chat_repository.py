from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.chat import Chat
from app.db.models.common import ChatKind


class ChatRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_for_user(self, user_id: str, *, include_deleted: bool = False) -> list[Chat]:
        stmt = select(Chat).where(Chat.user_id == user_id)
        if not include_deleted:
            stmt = stmt.where(Chat.is_deleted.is_(False))
        stmt = stmt.order_by(Chat.created_at.asc())
        return list(self._session.execute(stmt).scalars())

    def get_for_user(self, chat_id: str, user_id: str) -> Optional[Chat]:
        stmt = select(Chat).where(
            Chat.id == chat_id,
            Chat.user_id == user_id,
            Chat.is_deleted.is_(False),
        )
        return self._session.execute(stmt).scalar_one_or_none()

    def get_active_base_chat(self, user_id: str) -> Optional[Chat]:
        stmt = (
            select(Chat)
            .where(
                Chat.user_id == user_id,
                Chat.kind == ChatKind.BASE,
                Chat.is_deleted.is_(False),
                Chat.is_archived.is_(False),
            )
            .order_by(Chat.created_at.asc())
        )
        return self._session.execute(stmt).scalar_one_or_none()

    def list_base_chats(self, user_id: str) -> list[Chat]:
        stmt = (
            select(Chat)
            .where(Chat.user_id == user_id, Chat.kind == ChatKind.BASE, Chat.is_deleted.is_(False))
            .order_by(Chat.created_at.asc())
        )
        return list(self._session.execute(stmt).scalars())

    def create(
        self,
        *,
        user_id: str,
        title: str,
        kind: ChatKind = ChatKind.REGULAR,
        is_archived: bool = False,
    ) -> Chat:
        chat = Chat(
            user_id=user_id,
            title=title,
            kind=kind,
            is_archived=is_archived,
            is_deleted=False,
        )
        self._session.add(chat)
        self._session.flush()
        return chat

    def save(self, chat: Chat) -> Chat:
        self._session.add(chat)
        self._session.flush()
        return chat
