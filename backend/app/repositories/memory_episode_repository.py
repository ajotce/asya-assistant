from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db.models.common import MemoryStatus
from app.db.models.memory_episode import MemoryEpisode


class MemoryEpisodeRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_for_user(self, user_id: str, *, active_only: bool = True) -> list[MemoryEpisode]:
        stmt = select(MemoryEpisode).where(MemoryEpisode.user_id == user_id)
        if active_only:
            stmt = stmt.where(MemoryEpisode.status.notin_([MemoryStatus.FORBIDDEN, MemoryStatus.DELETED]))
        stmt = stmt.order_by(MemoryEpisode.created_at.desc())
        return list(self._session.execute(stmt).scalars())

    def create(
        self,
        *,
        user_id: str,
        chat_id: str,
        summary: str,
        status: MemoryStatus,
        source: str,
        space_id: str | None,
    ) -> MemoryEpisode:
        item = MemoryEpisode(
            user_id=user_id,
            chat_id=chat_id,
            summary=summary,
            status=status,
            source=source,
            space_id=space_id,
        )
        self._session.add(item)
        self._session.flush()
        return item

    def list_relevant_for_user_space(
        self,
        *,
        user_id: str,
        space_id: str | None,
        limit: int = 6,
    ) -> list[MemoryEpisode]:
        space_filter = MemoryEpisode.space_id.is_(None)
        if space_id is not None:
            space_filter = or_(space_filter, MemoryEpisode.space_id == space_id)
        stmt = (
            select(MemoryEpisode)
            .where(
                MemoryEpisode.user_id == user_id,
                MemoryEpisode.status.notin_([MemoryStatus.FORBIDDEN, MemoryStatus.DELETED]),
                space_filter,
            )
            .order_by(MemoryEpisode.created_at.desc())
            .limit(limit)
        )
        return list(self._session.execute(stmt).scalars())
