from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models.observed_entity_snapshot import ObservedEntitySnapshot
from app.db.models.observed_entity_state_change import ObservedEntityStateChange
from app.repositories.observed_entity_snapshot_repository import ObservedEntitySnapshotRepository
from app.repositories.observed_entity_state_change_repository import ObservedEntityStateChangeRepository


SENSITIVE_STATE_KEYS = {
    "subject",
    "body",
    "snippet",
    "content",
    "description",
    "raw",
    "token",
    "access_token",
    "refresh_token",
    "authorization",
}


@dataclass
class SnapshotCaptureResult:
    snapshot: ObservedEntitySnapshot
    state_change: ObservedEntityStateChange | None
    was_deduplicated: bool


class ObserverSnapshotService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._snapshots = ObservedEntitySnapshotRepository(session)
        self._changes = ObservedEntityStateChangeRepository(session)

    def capture_snapshot(
        self,
        *,
        user_id: str,
        provider: str,
        entity_type: str,
        entity_ref: str,
        normalized_state: dict[str, Any],
        observed_at: datetime | None = None,
    ) -> SnapshotCaptureResult:
        when = observed_at or datetime.now(timezone.utc)
        safe_state = self._sanitize_state(normalized_state)
        digest = self._compute_digest(safe_state)

        latest = self._snapshots.latest_for_entity(
            user_id=user_id,
            provider=provider,
            entity_type=entity_type,
            entity_ref=entity_ref,
        )
        if latest is not None and latest.digest == digest:
            return SnapshotCaptureResult(snapshot=latest, state_change=None, was_deduplicated=True)

        try:
            snapshot = self._snapshots.create(
                user_id=user_id,
                provider=provider,
                entity_type=entity_type,
                entity_ref=entity_ref,
                normalized_state=safe_state,
                observed_at=when,
                digest=digest,
            )
        except IntegrityError:
            self._session.rollback()
            existing = self._snapshots.latest_for_entity(
                user_id=user_id,
                provider=provider,
                entity_type=entity_type,
                entity_ref=entity_ref,
            )
            if existing is None:
                raise
            return SnapshotCaptureResult(snapshot=existing, state_change=None, was_deduplicated=True)

        state_change = self._build_state_change(
            user_id=user_id,
            provider=provider,
            entity_type=entity_type,
            entity_ref=entity_ref,
            previous=latest,
            current=snapshot,
        )
        return SnapshotCaptureResult(snapshot=snapshot, state_change=state_change, was_deduplicated=False)

    def enforce_retention(self, *, user_id: str, retention_days: int | None = None) -> int:
        settings = get_settings()
        days = retention_days or settings.observer_snapshot_retention_days
        if days <= 0:
            return 0
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        return self._snapshots.delete_older_than(user_id=user_id, cutoff=cutoff)

    def _build_state_change(
        self,
        *,
        user_id: str,
        provider: str,
        entity_type: str,
        entity_ref: str,
        previous: ObservedEntitySnapshot | None,
        current: ObservedEntitySnapshot,
    ) -> ObservedEntityStateChange:
        old_state = previous.normalized_state if previous is not None else {}
        new_state = current.normalized_state if isinstance(current.normalized_state, dict) else {}

        if previous is None:
            change_kind = "created"
            changed_fields = sorted(new_state.keys())
        else:
            changed_fields = sorted(
                key
                for key in set(old_state.keys()) | set(new_state.keys())
                if old_state.get(key) != new_state.get(key)
            )
            change_kind = "updated" if changed_fields else "unchanged"

        return self._changes.create(
            user_id=user_id,
            snapshot_id=current.id,
            previous_snapshot_id=(previous.id if previous is not None else None),
            provider=provider,
            entity_type=entity_type,
            entity_ref=entity_ref,
            change_kind=change_kind,
            changed_fields=changed_fields,
            old_state=old_state,
            new_state=new_state,
        )

    @staticmethod
    def _compute_digest(state: dict[str, Any]) -> str:
        payload = json.dumps(state, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @classmethod
    def _sanitize_state(cls, state: dict[str, Any]) -> dict[str, Any]:
        return cls._sanitize_value(state)

    @classmethod
    def _sanitize_value(cls, value: Any):
        if isinstance(value, dict):
            cleaned: dict[str, Any] = {}
            for key, inner in value.items():
                if key.lower() in SENSITIVE_STATE_KEYS:
                    continue
                cleaned[key] = cls._sanitize_value(inner)
            return cleaned
        if isinstance(value, list):
            return [cls._sanitize_value(item) for item in value]
        return value
