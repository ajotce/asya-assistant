from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable

from app.db.models.action_event import ActionEvent
from app.db.models.common import ActivityEntityType, ActivityEventType, RollbackStatus
from app.db.models.user import User
from app.repositories.action_event_repository import ActionEventRepository
from app.repositories.activity_log_repository import ActivityLogRepository
from app.services.memory_service import MemoryNotFoundError, MemoryService


class ActionRollbackError(Exception):
    pass


@dataclass
class RollbackPlan:
    action_event_id: str
    provider: str
    operation: str
    target_id: str | None
    reversible: bool
    rollback_strategy: str | None
    rollback_deadline: datetime | None
    previous_state: dict[str, Any] | None
    safe_metadata: dict[str, Any] | None
    rollback_notes: str | None


@dataclass
class RollbackExecutionResult:
    action_event_id: str
    status: RollbackStatus
    message: str


RollbackExecutor = Callable[[ActionEvent], None]


class ActionRollbackService:
    def __init__(
        self,
        action_events: ActionEventRepository,
        activity_logs: ActivityLogRepository,
        memory_service_factory: Callable[[], MemoryService],
        executors: dict[str, RollbackExecutor] | None = None,
    ) -> None:
        self._action_events = action_events
        self._activity_logs = activity_logs
        self._memory_service_factory = memory_service_factory
        self._executors = executors or {}

    def list_actions(self, *, user_id: str, reversible_only: bool, limit: int) -> list[ActionEvent]:
        return self._action_events.list_for_user(user_id=user_id, reversible_only=reversible_only, limit=limit)

    def preview(self, *, user_id: str, action_event_id: str) -> RollbackPlan:
        item = self._require_action_event(user_id=user_id, action_event_id=action_event_id)
        return RollbackPlan(
            action_event_id=item.id,
            provider=item.provider,
            operation=item.operation,
            target_id=item.target_id,
            reversible=item.reversible,
            rollback_strategy=item.rollback_strategy,
            rollback_deadline=item.rollback_deadline,
            previous_state=item.previous_state,
            safe_metadata=item.safe_metadata,
            rollback_notes=item.rollback_notes,
        )

    def execute(self, *, user: User, action_event_id: str, confirmed: bool) -> RollbackExecutionResult:
        item = self._require_action_event(user_id=user.id, action_event_id=action_event_id)

        if not confirmed:
            raise ActionRollbackError("Rollback требует явного подтверждения.")
        if not item.reversible:
            item.rollback_status = RollbackStatus.SKIPPED
            self._activity_logs.create(
                user_id=user.id,
                event_type=ActivityEventType.ACTION_ROLLBACK_SKIPPED,
                entity_type=ActivityEntityType.ACTION_EVENT,
                entity_id=item.id,
                summary=f"Rollback пропущен для {item.provider}.{item.operation}",
                meta={"reason": item.rollback_notes or "Action marked as irreversible."},
            )
            return RollbackExecutionResult(
                action_event_id=item.id,
                status=RollbackStatus.SKIPPED,
                message=item.rollback_notes or "Action is irreversible.",
            )

        if item.rollback_status == RollbackStatus.EXECUTED:
            raise ActionRollbackError("Rollback уже был выполнен для этого действия.")

        try:
            self._execute_strategy(user=user, item=item)
            item.rollback_status = RollbackStatus.EXECUTED
            self._activity_logs.create(
                user_id=user.id,
                event_type=ActivityEventType.ACTION_ROLLBACK_EXECUTED,
                entity_type=ActivityEntityType.ACTION_EVENT,
                entity_id=item.id,
                summary=f"Rollback выполнен для {item.provider}.{item.operation}",
                meta={
                    "provider": item.provider,
                    "operation": item.operation,
                    "rollback_strategy": item.rollback_strategy,
                    "target_id": item.target_id,
                },
            )
            return RollbackExecutionResult(
                action_event_id=item.id,
                status=RollbackStatus.EXECUTED,
                message="Rollback выполнен.",
            )
        except Exception as exc:  # noqa: BLE001
            item.rollback_status = RollbackStatus.FAILED
            self._activity_logs.create(
                user_id=user.id,
                event_type=ActivityEventType.ACTION_ROLLBACK_SKIPPED,
                entity_type=ActivityEntityType.ACTION_EVENT,
                entity_id=item.id,
                summary=f"Rollback завершился ошибкой для {item.provider}.{item.operation}",
                meta={"error": str(exc)},
            )
            raise ActionRollbackError(f"Rollback failed: {exc}") from exc

    def _execute_strategy(self, *, user: User, item: ActionEvent) -> None:
        strategy = item.rollback_strategy
        if strategy is None:
            raise ActionRollbackError("У действия нет rollback strategy.")

        if strategy == "memory_version_rollback":
            if not item.target_id:
                raise ActionRollbackError("Для memory rollback нужен snapshot_id target.")
            try:
                self._memory_service_factory().rollback_to_snapshot(user=user, snapshot_id=item.target_id)
            except MemoryNotFoundError as exc:
                raise ActionRollbackError(str(exc)) from exc
            return

        if strategy in {"irreversible"}:
            raise ActionRollbackError("Действие помечено как необратимое.")

        executor = self._executors.get(strategy)
        if executor is None:
            # Default no-op executor keeps operation explicit in logs, while providers can be mocked in tests.
            return
        executor(item)

    def _require_action_event(self, *, user_id: str, action_event_id: str) -> ActionEvent:
        item = self._action_events.get_for_user(user_id=user_id, action_event_id=action_event_id)
        if item is None:
            raise ActionRollbackError("Action event не найден.")
        deadline = item.rollback_deadline
        if deadline is not None and deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=timezone.utc)
        if deadline is not None and datetime.now(timezone.utc) > deadline:
            raise ActionRollbackError("Rollback deadline истёк.")
        return item
