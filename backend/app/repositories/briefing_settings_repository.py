from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.briefing_settings import BriefingSettings


class BriefingSettingsRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_user_id(self, user_id: str) -> BriefingSettings | None:
        stmt = select(BriefingSettings).where(BriefingSettings.user_id == user_id)
        return self._session.execute(stmt).scalar_one_or_none()

    def get_or_create_default(self, user_id: str) -> BriefingSettings:
        current = self.get_by_user_id(user_id)
        if current is not None:
            return current
        created = BriefingSettings(user_id=user_id)
        self._session.add(created)
        self._session.flush()
        return created

    def save(self, item: BriefingSettings) -> BriefingSettings:
        self._session.add(item)
        self._session.flush()
        return item
