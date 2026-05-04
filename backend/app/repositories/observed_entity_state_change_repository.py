from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.observed_entity_state_change import ObservedEntityStateChange


class ObservedEntityStateChangeRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(
        self,
        *,
        user_id: str,
        snapshot_id: str,
        previous_snapshot_id: str | None,
        provider: str,
        entity_type: str,
        entity_ref: str,
        change_kind: str,
        changed_fields: list[str],
        old_state: dict,
        new_state: dict,
    ) -> ObservedEntityStateChange:
        item = ObservedEntityStateChange(
            user_id=user_id,
            snapshot_id=snapshot_id,
            previous_snapshot_id=previous_snapshot_id,
            provider=provider,
            entity_type=entity_type,
            entity_ref=entity_ref,
            change_kind=change_kind,
            changed_fields=changed_fields,
            old_state=old_state,
            new_state=new_state,
        )
        self._session.add(item)
        self._session.flush()
        return item

    def list_for_entity(
        self,
        *,
        user_id: str,
        provider: str,
        entity_type: str,
        entity_ref: str,
        limit: int = 50,
    ) -> list[ObservedEntityStateChange]:
        stmt = (
            select(ObservedEntityStateChange)
            .where(
                ObservedEntityStateChange.user_id == user_id,
                ObservedEntityStateChange.provider == provider,
                ObservedEntityStateChange.entity_type == entity_type,
                ObservedEntityStateChange.entity_ref == entity_ref,
            )
            .order_by(ObservedEntityStateChange.created_at.desc())
            .limit(limit)
        )
        return list(self._session.execute(stmt).scalars())
