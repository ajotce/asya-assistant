from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.action_event import ActionEvent


class ActionEventRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, *, user_id: str, activity_log_id: str | None, provider: str, operation: str, target_id: str | None, reversible: bool, rollback_strategy: str | None, rollback_deadline: datetime | None, previous_state: dict | None, safe_metadata: dict | None, rollback_notes: str | None = None) -> ActionEvent:
        item = ActionEvent(
            user_id=user_id,
            activity_log_id=activity_log_id,
            provider=provider,
            operation=operation,
            target_id=target_id,
            reversible=reversible,
            rollback_strategy=rollback_strategy,
            rollback_deadline=rollback_deadline,
            previous_state=previous_state,
            safe_metadata=safe_metadata,
            rollback_notes=rollback_notes,
        )
        self._session.add(item)
        self._session.flush()
        return item

    def get_for_user(self, *, user_id: str, action_event_id: str) -> ActionEvent | None:
        stmt = select(ActionEvent).where(ActionEvent.id == action_event_id, ActionEvent.user_id == user_id)
        return self._session.execute(stmt).scalar_one_or_none()

    def list_for_user(self, *, user_id: str, reversible_only: bool, limit: int) -> list[ActionEvent]:
        stmt = select(ActionEvent).where(ActionEvent.user_id == user_id)
        if reversible_only:
            stmt = stmt.where(ActionEvent.reversible.is_(True))
        stmt = stmt.order_by(ActionEvent.created_at.desc()).limit(limit)
        return list(self._session.execute(stmt).scalars())
