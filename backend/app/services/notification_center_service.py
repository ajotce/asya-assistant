from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models.common import ActivityEntityType, ActivityEventType
from app.repositories.activity_log_repository import ActivityLogRepository


class NotificationCenterService:
    def __init__(self, session: Session) -> None:
        self._activity = ActivityLogRepository(session)

    def send_critical_observation(self, *, user_id: str, observation_id: str, title: str) -> None:
        self._activity.create(
            user_id=user_id,
            event_type=ActivityEventType.NOTIFICATION_CENTER,
            entity_type=ActivityEntityType.OBSERVATION,
            entity_id=observation_id,
            summary=f"Critical-наблюдение отправлено в Notification Center: {title}",
            meta={"level": "critical"},
        )
