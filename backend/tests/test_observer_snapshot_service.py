from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.db.models.common import UserStatus
from app.repositories.observed_entity_snapshot_repository import ObservedEntitySnapshotRepository
from app.repositories.observed_entity_state_change_repository import ObservedEntityStateChangeRepository
from app.repositories.user_repository import UserRepository
from app.services.observer_snapshot_service import ObserverSnapshotService
from tests.auth_helpers import setup_test_db


def _create_user(session: Session, *, email: str):
    user = UserRepository(session).create(
        email=email,
        display_name="Observer",
        password_hash="hash",
        status=UserStatus.ACTIVE,
    )
    session.commit()
    return user


def test_capture_snapshot_deduplicates_and_creates_change(monkeypatch, tmp_path) -> None:
    _, engine = setup_test_db(tmp_path, monkeypatch)

    with Session(bind=engine) as session:
        user = _create_user(session, email="observer@example.com")
        service = ObserverSnapshotService(session)

        first = service.capture_snapshot(
            user_id=user.id,
            provider="todoist",
            entity_type="task",
            entity_ref="task-1",
            normalized_state={"status": "open", "due_at": "2026-05-05T10:00:00Z", "subject": "secret"},
            observed_at=datetime(2026, 5, 4, 9, 0, tzinfo=timezone.utc),
        )
        assert first.was_deduplicated is False
        assert first.state_change is not None
        assert first.state_change.change_kind == "created"
        assert "subject" not in first.snapshot.normalized_state

        second = service.capture_snapshot(
            user_id=user.id,
            provider="todoist",
            entity_type="task",
            entity_ref="task-1",
            normalized_state={"status": "open", "due_at": "2026-05-05T10:00:00Z"},
            observed_at=datetime(2026, 5, 4, 9, 5, tzinfo=timezone.utc),
        )
        assert second.was_deduplicated is True

        third = service.capture_snapshot(
            user_id=user.id,
            provider="todoist",
            entity_type="task",
            entity_ref="task-1",
            normalized_state={"status": "rescheduled", "due_at": "2026-05-06T10:00:00Z"},
            observed_at=datetime(2026, 5, 4, 9, 10, tzinfo=timezone.utc),
        )
        assert third.was_deduplicated is False
        assert third.state_change is not None
        assert third.state_change.change_kind == "updated"
        assert third.state_change.changed_fields == ["due_at", "status"]

        session.commit()

        snapshots = ObservedEntitySnapshotRepository(session).list_for_entity(
            user_id=user.id,
            provider="todoist",
            entity_type="task",
            entity_ref="task-1",
            limit=10,
        )
        assert len(snapshots) == 2

        changes = ObservedEntityStateChangeRepository(session).list_for_entity(
            user_id=user.id,
            provider="todoist",
            entity_type="task",
            entity_ref="task-1",
            limit=10,
        )
        assert len(changes) == 2


def test_enforce_retention_removes_old_snapshots(monkeypatch, tmp_path) -> None:
    _, engine = setup_test_db(tmp_path, monkeypatch)

    with Session(bind=engine) as session:
        user = _create_user(session, email="retention@example.com")
        service = ObserverSnapshotService(session)

        old_time = datetime.now(timezone.utc) - timedelta(days=45)
        recent_time = datetime.now(timezone.utc) - timedelta(days=2)

        service.capture_snapshot(
            user_id=user.id,
            provider="google_calendar",
            entity_type="event",
            entity_ref="event-1",
            normalized_state={"starts_at": "2026-04-01T09:00:00Z"},
            observed_at=old_time,
        )
        service.capture_snapshot(
            user_id=user.id,
            provider="google_calendar",
            entity_type="event",
            entity_ref="event-2",
            normalized_state={"starts_at": "2026-05-10T09:00:00Z"},
            observed_at=recent_time,
        )
        session.commit()

        removed = service.enforce_retention(user_id=user.id, retention_days=30)
        assert removed == 1
        session.commit()

        all_recent = ObservedEntitySnapshotRepository(session).list_for_entity(
            user_id=user.id,
            provider="google_calendar",
            entity_type="event",
            entity_ref="event-2",
            limit=10,
        )
        assert len(all_recent) == 1
