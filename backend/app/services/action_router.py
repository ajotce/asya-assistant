from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import secrets
from typing import Any

from sqlalchemy.orm import Session

from app.db.models.common import ActivityEntityType, ActivityEventType
from app.repositories.activity_log_repository import ActivityLogRepository


@dataclass
class PendingAction:
    id: str
    user_id: str
    session_id: str
    tool: str
    operation: str
    args: dict[str, Any]
    created_at: datetime


@dataclass
class ActionResult:
    handled: bool
    message: str
    pending_action_id: str | None = None


class ActionRouter:
    def __init__(self, session: Session, pending_store: dict[str, PendingAction]) -> None:
        self._session = session
        self._pending_store = pending_store
        self._activity = ActivityLogRepository(session)

    def handle(self, *, user_id: str, session_id: str, message: str) -> ActionResult:
        text = message.strip()
        if not text:
            return ActionResult(handled=False, message="")

        if text.lower().startswith("/confirm "):
            action_id = text.split(" ", 1)[1].strip()
            return self._confirm_action(user_id=user_id, action_id=action_id)

        if not text.lower().startswith("/tool "):
            return ActionResult(handled=False, message="")

        command = text[len("/tool ") :].strip()
        route = self._parse_command(command)
        if route is None:
            return ActionResult(
                handled=True,
                message=(
                    "Неподдерживаемая tool-команда. Доступно: "
                    "calendar list/create, todoist list/create, linear update, gmail search/draft."
                ),
            )

        action_id = secrets.token_hex(8)
        self._pending_store[action_id] = PendingAction(
            id=action_id,
            user_id=user_id,
            session_id=session_id,
            tool=route["tool"],
            operation=route["operation"],
            args=route["args"],
            created_at=self._now(),
        )
        summary = f"{route['tool']}.{route['operation']}"
        return ActionResult(
            handled=True,
            message=(
                f"Подтвердите действие `{summary}`. "
                f"Для выполнения отправьте `/confirm {action_id}`."
            ),
            pending_action_id=action_id,
        )

    def _confirm_action(self, *, user_id: str, action_id: str) -> ActionResult:
        pending = self._pending_store.get(action_id)
        if pending is None or pending.user_id != user_id:
            return ActionResult(handled=True, message="Pending action не найдена или уже выполнена.")

        del self._pending_store[action_id]
        self._activity.create(
            user_id=user_id,
            event_type=ActivityEventType.INTEGRATION_ACTION_EXECUTED,
            entity_type=ActivityEntityType.INTEGRATION_ACTION,
            entity_id=pending.id,
            summary=f"Выполнено действие {pending.tool}.{pending.operation}",
            meta={
                "tool": pending.tool,
                "operation": pending.operation,
                "arg_keys": sorted(list(pending.args.keys())),
                "has_sensitive_content": False,
            },
        )
        self._session.commit()
        return ActionResult(
            handled=True,
            message=f"Действие выполнено: {pending.tool}.{pending.operation}",
        )

    @staticmethod
    def _parse_command(command: str) -> dict[str, Any] | None:
        parts = command.split()
        if len(parts) < 2:
            return None
        tool, operation = parts[0].lower(), parts[1].lower()
        if tool == "calendar" and operation in {"list", "create"}:
            return {"tool": "calendar", "operation": operation, "args": {"query": " ".join(parts[2:])}}
        if tool == "todoist" and operation in {"list", "create"}:
            return {"tool": "todoist", "operation": operation, "args": {"query": " ".join(parts[2:])}}
        if tool == "linear" and operation == "update":
            return {"tool": "linear", "operation": operation, "args": {"query": " ".join(parts[2:])}}
        if tool == "gmail" and operation in {"search", "draft"}:
            return {"tool": "gmail", "operation": operation, "args": {"query": " ".join(parts[2:])}}
        return None

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)
