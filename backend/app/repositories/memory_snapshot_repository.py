from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.memory_snapshot import MemorySnapshot


class MemorySnapshotRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_for_user(self, user_id: str, *, space_id: str | None = None, limit: int = 100) -> list[MemorySnapshot]:
        stmt = select(MemorySnapshot).where(MemorySnapshot.user_id == user_id)
        if space_id is not None:
            stmt = stmt.where(MemorySnapshot.space_id == space_id)
        stmt = stmt.order_by(MemorySnapshot.created_at.desc()).limit(limit)
        return list(self._session.execute(stmt).scalars())

    def get_for_user(self, snapshot_id: str, user_id: str) -> MemorySnapshot | None:
        stmt = select(MemorySnapshot).where(
            MemorySnapshot.id == snapshot_id,
            MemorySnapshot.user_id == user_id,
        )
        return self._session.execute(stmt).scalar_one_or_none()

    def latest_for_user(self, user_id: str) -> MemorySnapshot | None:
        stmt = (
            select(MemorySnapshot)
            .where(MemorySnapshot.user_id == user_id)
            .order_by(MemorySnapshot.created_at.desc())
            .limit(1)
        )
        return self._session.execute(stmt).scalar_one_or_none()

    def create(self, *, user_id: str, label: str, payload: dict, space_id: str | None = None) -> MemorySnapshot:
        item = MemorySnapshot(
            user_id=user_id,
            space_id=space_id,
            label=label,
            payload=payload,
        )
        self._session.add(item)
        self._session.flush()
        return item
