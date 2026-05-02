from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.common import ObservationStatus
from app.db.models.observation import Observation


class ObservationRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_for_user(
        self,
        user_id: str,
        *,
        status: ObservationStatus | None = None,
        detector: str | None = None,
        limit: int = 100,
    ) -> list[Observation]:
        stmt = select(Observation).where(Observation.user_id == user_id)
        if status is not None:
            stmt = stmt.where(Observation.status == status)
        if detector:
            stmt = stmt.where(Observation.detector == detector)
        stmt = stmt.order_by(Observation.observed_at.desc()).limit(limit)
        return list(self._session.execute(stmt).scalars())

    def get_for_user(self, observation_id: str, user_id: str) -> Observation | None:
        stmt = select(Observation).where(Observation.id == observation_id, Observation.user_id == user_id)
        return self._session.execute(stmt).scalar_one_or_none()

    def get_recent_duplicate(
        self,
        *,
        user_id: str,
        detector: str,
        dedup_key: str,
        within_minutes: int = 180,
    ) -> Observation | None:
        since = datetime.now(timezone.utc) - timedelta(minutes=within_minutes)
        stmt = (
            select(Observation)
            .where(
                Observation.user_id == user_id,
                Observation.detector == detector,
                Observation.dedup_key == dedup_key,
                Observation.observed_at >= since,
                Observation.status.in_((ObservationStatus.NEW, ObservationStatus.SEEN)),
            )
            .order_by(Observation.observed_at.desc())
        )
        return self._session.execute(stmt).scalar_one_or_none()

    def create(
        self,
        *,
        user_id: str,
        detector: str,
        title: str,
        details: str,
        severity,
        status,
        context_payload: dict,
        dedup_key: str,
        observed_at: datetime,
        rule_id: str | None = None,
    ) -> Observation:
        item = Observation(
            user_id=user_id,
            rule_id=rule_id,
            detector=detector,
            title=title,
            details=details,
            severity=severity,
            status=status,
            context_payload=context_payload,
            dedup_key=dedup_key,
            observed_at=observed_at,
        )
        self._session.add(item)
        self._session.flush()
        return item

    def save(self, item: Observation) -> Observation:
        self._session.add(item)
        self._session.flush()
        return item
