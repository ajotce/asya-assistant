from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete, distinct, select
from sqlalchemy.orm import Session

from app.db.models.observed_entity_snapshot import ObservedEntitySnapshot


class ObservedEntitySnapshotRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(
        self,
        *,
        user_id: str,
        provider: str,
        entity_type: str,
        entity_ref: str,
        normalized_state: dict,
        observed_at: datetime,
        digest: str,
    ) -> ObservedEntitySnapshot:
        item = ObservedEntitySnapshot(
            user_id=user_id,
            provider=provider,
            entity_type=entity_type,
            entity_ref=entity_ref,
            normalized_state=normalized_state,
            observed_at=observed_at,
            digest=digest,
        )
        self._session.add(item)
        self._session.flush()
        return item

    def latest_for_entity(self, *, user_id: str, provider: str, entity_type: str, entity_ref: str) -> ObservedEntitySnapshot | None:
        stmt = (
            select(ObservedEntitySnapshot)
            .where(
                ObservedEntitySnapshot.user_id == user_id,
                ObservedEntitySnapshot.provider == provider,
                ObservedEntitySnapshot.entity_type == entity_type,
                ObservedEntitySnapshot.entity_ref == entity_ref,
            )
            .order_by(ObservedEntitySnapshot.observed_at.desc())
            .limit(1)
        )
        return self._session.execute(stmt).scalar_one_or_none()

    def list_for_entity(
        self,
        *,
        user_id: str,
        provider: str,
        entity_type: str,
        entity_ref: str,
        limit: int = 30,
    ) -> list[ObservedEntitySnapshot]:
        stmt = (
            select(ObservedEntitySnapshot)
            .where(
                ObservedEntitySnapshot.user_id == user_id,
                ObservedEntitySnapshot.provider == provider,
                ObservedEntitySnapshot.entity_type == entity_type,
                ObservedEntitySnapshot.entity_ref == entity_ref,
            )
            .order_by(ObservedEntitySnapshot.observed_at.desc())
            .limit(limit)
        )
        return list(self._session.execute(stmt).scalars())

    def delete_older_than(self, *, user_id: str, cutoff: datetime) -> int:
        stmt = delete(ObservedEntitySnapshot).where(
            ObservedEntitySnapshot.user_id == user_id,
            ObservedEntitySnapshot.observed_at < cutoff,
        )
        result = self._session.execute(stmt)
        return int(result.rowcount or 0)

    def list_entity_refs(self, *, user_id: str, provider: str, entity_type: str) -> list[str]:
        stmt = (
            select(distinct(ObservedEntitySnapshot.entity_ref))
            .where(
                ObservedEntitySnapshot.user_id == user_id,
                ObservedEntitySnapshot.provider == provider,
                ObservedEntitySnapshot.entity_type == entity_type,
            )
            .order_by(ObservedEntitySnapshot.entity_ref.asc())
        )
        return [str(row[0]) for row in self._session.execute(stmt).all() if row[0] is not None]
