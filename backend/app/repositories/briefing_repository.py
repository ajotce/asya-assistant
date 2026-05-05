from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.briefing import Briefing


class BriefingRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_for_user(self, user_id: str, *, limit: int = 20) -> list[Briefing]:
        stmt = (
            select(Briefing)
            .where(Briefing.user_id == user_id)
            .order_by(Briefing.created_at.desc())
            .limit(limit)
        )
        return list(self._session.execute(stmt).scalars())

    def get_for_user(self, briefing_id: str, user_id: str) -> Briefing | None:
        stmt = select(Briefing).where(Briefing.id == briefing_id, Briefing.user_id == user_id)
        return self._session.execute(stmt).scalar_one_or_none()

    def create(
        self,
        *,
        user_id: str,
        kind: str,
        title: str,
        content_markdown: str,
        delivered_in_app: bool,
        delivered_telegram: bool,
        source_meta: dict,
    ) -> Briefing:
        item = Briefing(
            user_id=user_id,
            kind=kind,
            title=title,
            content_markdown=content_markdown,
            delivered_in_app=delivered_in_app,
            delivered_telegram=delivered_telegram,
            source_meta=source_meta,
        )
        self._session.add(item)
        self._session.flush()
        return item
