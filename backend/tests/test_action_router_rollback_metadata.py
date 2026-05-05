from __future__ import annotations

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.models.action_event import ActionEvent
from app.db.models.common import UserRole, UserStatus
from app.db.models.user import User
from app.services.action_router import ActionRouter


def _make_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return Session(bind=engine)


def _make_user(session: Session) -> User:
    user = User(
        email="router@test.local",
        display_name="Router",
        password_hash="hash",
        role=UserRole.USER,
        status=UserStatus.ACTIVE,
    )
    session.add(user)
    session.flush()
    return user


def test_confirm_creates_action_event_with_reversible_metadata() -> None:
    session = _make_session()
    user = _make_user(session)
    pending: dict = {}
    router = ActionRouter(session, pending)

    prepare = router.handle(
        user_id=user.id,
        session_id="sess-1",
        message='/tool todoist update target_id=task-1 previous_state={"content":"old"}',
    )
    assert prepare.pending_action_id is not None

    confirmed = router.handle(
        user_id=user.id,
        session_id="sess-1",
        message=f"/confirm {prepare.pending_action_id}",
    )
    assert confirmed.handled is True

    event = session.execute(select(ActionEvent)).scalar_one()
    assert event.provider == "todoist"
    assert event.operation == "update"
    assert event.reversible is True
    assert event.rollback_strategy == "todoist_update_restore_fields"
    assert event.previous_state == {"content": "old"}


def test_irreversible_email_action_is_marked() -> None:
    session = _make_session()
    user = _make_user(session)
    pending: dict = {}
    router = ActionRouter(session, pending)

    prepare = router.handle(user_id=user.id, session_id="sess-1", message="/tool gmail draft hello")
    assert prepare.pending_action_id is not None
    router.handle(user_id=user.id, session_id="sess-1", message=f"/confirm {prepare.pending_action_id}")

    event = session.execute(select(ActionEvent)).scalar_one()
    assert event.reversible is False
    assert "не откатываются" in (event.rollback_notes or "")
