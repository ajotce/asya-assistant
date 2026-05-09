from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models.briefing import Briefing
from app.db.models.common import BriefingKind


class BriefingRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, *, user_id: str, kind: BriefingKind, content: str, delivered_via: list[str]) -> Briefing:
        item = Briefing(user_id=user_id, kind=kind, content=content, delivered_via=delivered_via)
        self._session.add(item)
        self._session.flush()
        return item

    def list_recent_for_user(self, *, user_id: str, since: datetime, limit: int = 100) -> list[Briefing]:
        stmt = (
            select(Briefing)
            .where(Briefing.user_id == user_id, Briefing.created_at >= since)
            .order_by(Briefing.created_at.desc())
            .limit(limit)
        )
        return list(self._session.execute(stmt).scalars())

    def get_for_user(self, *, user_id: str, briefing_id: str) -> Briefing | None:
        stmt = select(Briefing).where(Briefing.id == briefing_id, Briefing.user_id == user_id)
        return self._session.execute(stmt).scalar_one_or_none()

    def delete_older_than(self, *, cutoff: datetime) -> int:
        stmt = delete(Briefing).where(Briefing.created_at < cutoff)
        result = self._session.execute(stmt)
        return int(result.rowcount or 0)
