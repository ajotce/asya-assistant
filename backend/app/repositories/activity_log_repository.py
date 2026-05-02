from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.activity_log import ActivityLog
from app.db.models.common import ActivityEntityType, ActivityEventType


class ActivityLogRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_for_user(
        self,
        user_id: str,
        *,
        limit: int = 100,
        event_type: ActivityEventType | None = None,
        entity_type: ActivityEntityType | None = None,
        space_id: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> list[ActivityLog]:
        stmt = select(ActivityLog).where(ActivityLog.user_id == user_id)
        if event_type is not None:
            stmt = stmt.where(ActivityLog.event_type == event_type)
        if entity_type is not None:
            stmt = stmt.where(ActivityLog.entity_type == entity_type)
        if space_id is not None:
            stmt = stmt.where(ActivityLog.space_id == space_id)
        if date_from is not None:
            stmt = stmt.where(ActivityLog.created_at >= date_from)
        if date_to is not None:
            stmt = stmt.where(ActivityLog.created_at <= date_to)
        stmt = stmt.order_by(ActivityLog.created_at.desc()).limit(limit)
        return list(self._session.execute(stmt).scalars())

    def create(
        self,
        *,
        user_id: str,
        event_type: ActivityEventType,
        entity_type: ActivityEntityType,
        entity_id: str,
        summary: str,
        space_id: str | None = None,
        meta: dict | None = None,
    ) -> ActivityLog:
        item = ActivityLog(
            user_id=user_id,
            space_id=space_id,
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            summary=summary,
            meta=meta,
        )
        self._session.add(item)
        self._session.flush()
        return item
