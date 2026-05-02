from __future__ import annotations

from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models.message import Message


class MessageRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_for_chat(self, chat_id: str) -> list[Message]:
        stmt = select(Message).where(Message.chat_id == chat_id).order_by(Message.created_at.asc())
        return list(self._session.execute(stmt).scalars())

    def count_for_chat(self, chat_id: str) -> int:
        stmt = select(func.count(Message.id)).where(Message.chat_id == chat_id)
        value = self._session.execute(stmt).scalar_one()
        return int(value)

    def create(self, *, chat_id: str, user_id: Optional[str], role: str, content: str) -> Message:
        message = Message(chat_id=chat_id, user_id=user_id, role=role, content=content)
        self._session.add(message)
        self._session.flush()
        return message
