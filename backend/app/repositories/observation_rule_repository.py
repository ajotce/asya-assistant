from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.observation_rule import ObservationRule


class ObservationRuleRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_for_user(self, user_id: str, *, only_enabled: bool = True) -> list[ObservationRule]:
        stmt = select(ObservationRule).where(ObservationRule.user_id == user_id)
        if only_enabled:
            stmt = stmt.where(ObservationRule.enabled.is_(True))
        stmt = stmt.order_by(ObservationRule.created_at.desc())
        return list(self._session.execute(stmt).scalars())

    def get_for_user(self, rule_id: str, user_id: str) -> ObservationRule | None:
        stmt = select(ObservationRule).where(ObservationRule.id == rule_id, ObservationRule.user_id == user_id)
        return self._session.execute(stmt).scalar_one_or_none()

    def get_by_detector_for_user(self, user_id: str, detector: str) -> ObservationRule | None:
        stmt = select(ObservationRule).where(ObservationRule.user_id == user_id, ObservationRule.detector == detector)
        return self._session.execute(stmt).scalar_one_or_none()

    def save(self, item: ObservationRule) -> ObservationRule:
        self._session.add(item)
        self._session.flush()
        return item
