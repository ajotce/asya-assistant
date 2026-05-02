from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db.models.diary_entry import DiaryEntry


class DiaryEntryRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_for_user(self, user_id: str, *, query: str | None = None, limit: int = 100) -> list[DiaryEntry]:
        stmt = select(DiaryEntry).where(DiaryEntry.user_id == user_id, DiaryEntry.is_deleted.is_(False))
        if query and query.strip():
            pattern = f"%{query.strip()}%"
            stmt = stmt.where(
                or_(
                    DiaryEntry.title.ilike(pattern),
                    DiaryEntry.content.ilike(pattern),
                    DiaryEntry.transcript.ilike(pattern),
                )
            )
        stmt = stmt.order_by(DiaryEntry.created_at.desc()).limit(limit)
        return list(self._session.execute(stmt).scalars())

    def get_for_user(self, entry_id: str, user_id: str) -> DiaryEntry | None:
        stmt = select(DiaryEntry).where(
            DiaryEntry.id == entry_id,
            DiaryEntry.user_id == user_id,
            DiaryEntry.is_deleted.is_(False),
        )
        return self._session.execute(stmt).scalar_one_or_none()

    def create(
        self,
        *,
        user_id: str,
        title: str,
        content: str,
        source_audio_path: str | None,
        duration_seconds: int | None,
    ) -> DiaryEntry:
        item = DiaryEntry(
            user_id=user_id,
            title=title,
            content=content,
            source_audio_path=source_audio_path,
            duration_seconds=duration_seconds,
        )
        self._session.add(item)
        self._session.flush()
        return item

    def save(self, item: DiaryEntry) -> DiaryEntry:
        self._session.add(item)
        self._session.flush()
        return item
