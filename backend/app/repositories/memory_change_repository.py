from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models.memory_change import MemoryChange


class MemoryChangeRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_for_user(self, user_id: str) -> list[MemoryChange]:
        stmt = select(MemoryChange).where(MemoryChange.user_id == user_id).order_by(MemoryChange.created_at.desc())
        return list(self._session.execute(stmt).scalars())

    def create(self, *, user_id: str, space_id: str | None, entity_type: str, entity_id: str, change_kind, old_value: dict | None, new_value: dict | None) -> MemoryChange:
        item = MemoryChange(
            user_id=user_id,
            space_id=space_id,
            entity_type=entity_type,
            entity_id=entity_id,
            change_kind=change_kind,
            old_value=old_value,
            new_value=new_value,
        )
        self._session.add(item)
        self._session.flush()
        return item

    def count_for_user_since(self, user_id: str, *, date_from: datetime) -> int:
        stmt = select(func.count()).select_from(MemoryChange).where(
            MemoryChange.user_id == user_id,
            MemoryChange.created_at >= date_from,
        )
        return int(self._session.execute(stmt).scalar_one())
