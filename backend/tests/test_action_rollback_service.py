from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.models.action_event import ActionEvent
from app.db.models.common import RollbackStatus, UserRole, UserStatus
from app.db.models.user import User
from app.repositories.action_event_repository import ActionEventRepository
from app.repositories.activity_log_repository import ActivityLogRepository
from app.services.action_rollback_service import ActionRollbackError, ActionRollbackService


class _DummyMemoryService:
    def rollback_to_snapshot(self, *, user: User, snapshot_id: str):  # noqa: ANN201
        return None


def _make_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return Session(bind=engine)


def _make_user(session: Session) -> User:
    user = User(
        email="rollback@test.local",
        display_name="Rollback",
        password_hash="hash",
        role=UserRole.USER,
        status=UserStatus.ACTIVE,
    )
    session.add(user)
    session.flush()
    return user


def test_execute_reversible_action_success() -> None:
    session = _make_session()
    user = _make_user(session)
    repo = ActionEventRepository(session)

    event = repo.create(
        user_id=user.id,
        activity_log_id=None,
        provider="todoist",
        operation="update",
        target_id="task-1",
        reversible=True,
        rollback_strategy="todoist_update_restore_fields",
        rollback_deadline=None,
        previous_state={"content": "old"},
        safe_metadata={"arg_keys": ["target_id", "previous_state"]},
    )

    service = ActionRollbackService(
        action_events=repo,
        activity_logs=ActivityLogRepository(session),
        memory_service_factory=lambda: _DummyMemoryService(),
    )
    result = service.execute(user=user, action_event_id=event.id, confirmed=True)

    assert result.status == RollbackStatus.EXECUTED
    assert repo.get_for_user(user_id=user.id, action_event_id=event.id).rollback_status == RollbackStatus.EXECUTED


def test_execute_irreversible_action_marked_skipped() -> None:
    session = _make_session()
    user = _make_user(session)
    repo = ActionEventRepository(session)

    event = repo.create(
        user_id=user.id,
        activity_log_id=None,
        provider="gmail",
        operation="send",
        target_id="msg-1",
        reversible=False,
        rollback_strategy="irreversible",
        rollback_deadline=None,
        previous_state=None,
        safe_metadata={"reason": "external visible message"},
        rollback_notes="Отправленные email не откатываются.",
    )

    service = ActionRollbackService(
        action_events=repo,
        activity_logs=ActivityLogRepository(session),
        memory_service_factory=lambda: _DummyMemoryService(),
    )
    result = service.execute(user=user, action_event_id=event.id, confirmed=True)

    assert result.status == RollbackStatus.SKIPPED
    assert "не откатываются" in result.message


def test_execute_requires_confirmation() -> None:
    session = _make_session()
    user = _make_user(session)
    repo = ActionEventRepository(session)

    event = repo.create(
        user_id=user.id,
        activity_log_id=None,
        provider="linear",
        operation="update",
        target_id="issue-1",
        reversible=True,
        rollback_strategy="linear_update_restore_fields",
        rollback_deadline=None,
        previous_state={"title": "before"},
        safe_metadata=None,
    )

    service = ActionRollbackService(
        action_events=repo,
        activity_logs=ActivityLogRepository(session),
        memory_service_factory=lambda: _DummyMemoryService(),
    )

    try:
        service.execute(user=user, action_event_id=event.id, confirmed=False)
        assert False, "expected ActionRollbackError"
    except ActionRollbackError as exc:
        assert "подтверждения" in str(exc)


def test_list_reversible_only() -> None:
    session = _make_session()
    user = _make_user(session)
    repo = ActionEventRepository(session)

    repo.create(
        user_id=user.id,
        activity_log_id=None,
        provider="todoist",
        operation="create",
        target_id="task-2",
        reversible=True,
        rollback_strategy="todoist_create_delete_or_close",
        rollback_deadline=None,
        previous_state=None,
        safe_metadata=None,
    )
    repo.create(
        user_id=user.id,
        activity_log_id=None,
        provider="gmail",
        operation="send",
        target_id="msg-2",
        reversible=False,
        rollback_strategy="irreversible",
        rollback_deadline=None,
        previous_state=None,
        safe_metadata=None,
    )

    service = ActionRollbackService(
        action_events=repo,
        activity_logs=ActivityLogRepository(session),
        memory_service_factory=lambda: _DummyMemoryService(),
    )

    items = service.list_actions(user_id=user.id, reversible_only=True, limit=100)
    assert len(items) == 1
    assert items[0].provider == "todoist"
