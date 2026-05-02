from __future__ import annotations

from typing import Optional

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db.models.common import MemoryStatus
from app.db.models.user_profile_fact import UserProfileFact


class UserProfileFactRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_for_user(self, user_id: str, *, include_deleted: bool = False) -> list[UserProfileFact]:
        stmt = select(UserProfileFact).where(UserProfileFact.user_id == user_id)
        if not include_deleted:
            stmt = stmt.where(UserProfileFact.status != MemoryStatus.DELETED)
        stmt = stmt.order_by(UserProfileFact.created_at.desc())
        return list(self._session.execute(stmt).scalars())

    def get_for_user(self, fact_id: str, user_id: str) -> Optional[UserProfileFact]:
        stmt = select(UserProfileFact).where(UserProfileFact.id == fact_id, UserProfileFact.user_id == user_id)
        return self._session.execute(stmt).scalar_one_or_none()

    def create(
        self,
        *,
        user_id: str,
        key: str,
        value: str,
        status: MemoryStatus = MemoryStatus.NEEDS_REVIEW,
        source: str = "assistant",
        space_id: str | None = None,
    ) -> UserProfileFact:
        fact = UserProfileFact(
            user_id=user_id,
            space_id=space_id,
            key=key,
            value=value,
            status=status,
            source=source,
        )
        self._session.add(fact)
        self._session.flush()
        return fact

    def save(self, fact: UserProfileFact) -> UserProfileFact:
        self._session.add(fact)
        self._session.flush()
        return fact

    def list_active_for_user_space(
        self,
        *,
        user_id: str,
        space_id: str | None,
        limit: int = 20,
    ) -> list[UserProfileFact]:
        space_filter = UserProfileFact.space_id.is_(None)
        if space_id is not None:
            space_filter = or_(space_filter, UserProfileFact.space_id == space_id)
        stmt = (
            select(UserProfileFact)
            .where(
                UserProfileFact.user_id == user_id,
                UserProfileFact.status.notin_([MemoryStatus.FORBIDDEN, MemoryStatus.DELETED]),
                space_filter,
            )
            .order_by(UserProfileFact.created_at.desc())
            .limit(limit)
        )
        return list(self._session.execute(stmt).scalars())
