from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.db.models.common import ActivityEntityType, ActivityEventType
from app.db.models.user import User
from app.repositories.activity_log_repository import ActivityLogRepository


@dataclass
class NotificationEvent:
    user_id: str
    title: str
    body: str
    channel: str
    metadata: dict | None = None


class NotificationChannel:
    name: str

    def send(self, event: NotificationEvent) -> None:
        raise NotImplementedError


class NotificationCenter:
    def __init__(self, session: Session, channels: list[NotificationChannel] | None = None) -> None:
        self._session = session
        self._channels = channels or []
        self._activity = ActivityLogRepository(session)

    def register_channel(self, channel: NotificationChannel) -> None:
        self._channels.append(channel)

    def notify_user(self, user: User, *, title: str, body: str, channel: str, metadata: dict | None = None) -> None:
        event = NotificationEvent(
            user_id=user.id,
            title=title[:200],
            body=body[:1000],
            channel=channel,
            metadata=metadata,
        )
        for ch in self._channels:
            if ch.name == channel:
                ch.send(event)
                break
        self._activity.create(
            user_id=user.id,
            space_id=None,
            event_type=ActivityEventType.NOTIFICATION_SENT,
            entity_type=ActivityEntityType.NOTIFICATION,
            entity_id=f"notification-{int(datetime.now(timezone.utc).timestamp())}",
            summary=f"Уведомление отправлено в канал {channel}",
            meta={
                "title": event.title,
                "channel": channel,
                "metadata": metadata or {},
            },
        )
        self._session.flush()
