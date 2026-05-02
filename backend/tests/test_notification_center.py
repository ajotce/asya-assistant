from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.base import Base
from app.db.models.common import UserRole, UserStatus
from app.db.models.user import User
from app.db.session import get_engine
from app.notifications.notification_center import NotificationCenter, NotificationChannel, NotificationEvent


class _MockChannel(NotificationChannel):
    name = "test_channel"
    sent_events: list[NotificationEvent] = []

    def send(self, event: NotificationEvent) -> None:
        self.sent_events.append(event)


@pytest.fixture
def test_session(tmp_path, monkeypatch):
    db_path = tmp_path / "notify-test.sqlite3"
    monkeypatch.setenv("ASYA_DB_PATH", db_path.as_posix())
    get_settings.cache_clear()
    get_engine.cache_clear()
    settings = get_settings()
    engine = get_engine(settings.asya_db_url)
    Base.metadata.create_all(engine)
    session = Session(bind=engine)
    yield session
    session.close()
    get_settings.cache_clear()
    get_engine.cache_clear()


def test_notification_center_dispatches_to_channel(test_session):
    session = test_session
    user = User(
        id="n-user", email="notify@test.com", display_name="N",
        role=UserRole.USER, status=UserStatus.ACTIVE,
    )
    session.add(user)
    session.flush()

    channel = _MockChannel()
    channel.sent_events.clear()
    center = NotificationCenter(session, channels=[channel])
    center.notify_user(user, title="Test", body="Hello", channel="test_channel")

    assert len(channel.sent_events) == 1
    assert channel.sent_events[0].title == "Test"
    assert channel.sent_events[0].body == "Hello"
    assert channel.sent_events[0].user_id == "n-user"


def test_notification_center_skips_unknown_channel(test_session):
    session = test_session
    user = User(
        id="n-user-2", email="notify2@test.com", display_name="N2",
        role=UserRole.USER, status=UserStatus.ACTIVE,
    )
    session.add(user)
    session.flush()

    channel = _MockChannel()
    channel.sent_events.clear()
    center = NotificationCenter(session, channels=[channel])
    center.notify_user(user, title="T", body="B", channel="other")

    assert len(channel.sent_events) == 0


def test_notification_center_logs_activity(test_session):
    session = test_session
    user = User(
        id="n-user-3", email="notify3@test.com", display_name="N3",
        role=UserRole.USER, status=UserStatus.ACTIVE,
    )
    session.add(user)
    session.flush()

    channel = _MockChannel()
    channel.sent_events.clear()
    center = NotificationCenter(session, channels=[channel])
    center.notify_user(user, title="Alert", body="Something happened", channel="test_channel")

    from app.repositories.activity_log_repository import ActivityLogRepository
    logs = ActivityLogRepository(session).list_for_user(user.id, limit=5)
    notification_logs = [l for l in logs if l.event_type == "notification_sent"]
    assert len(notification_logs) >= 1
