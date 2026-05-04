from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import re
import secrets
from typing import Any, Callable

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


@dataclass
class ParsedRoute:
    tool: str
    operation: str
    args: dict[str, Any]
    requires_confirmation: bool


class ActionRouter:
    def __init__(
        self,
        session: Session,
        pending_store: dict[str, PendingAction],
        tool_handlers: dict[tuple[str, str], Callable[..., Any]] | None = None,
    ) -> None:
        self._session = session
        self._pending_store = pending_store
        self._activity = ActivityLogRepository(session)
        self._tool_handlers = tool_handlers or {}

    def handle(self, *, user_id: str, session_id: str, message: str) -> ActionResult:
        text = message.strip()
        if not text:
            return ActionResult(handled=False, message="")

        if text.lower().startswith("/confirm "):
            action_id = text.split(" ", 1)[1].strip()
            return self._confirm_action(user_id=user_id, action_id=action_id)

        route = self._parse_message(text)
        if route is None:
            if text.lower().startswith("/tool "):
                return ActionResult(handled=True, message="Неподдерживаемая tool-команда.")
            return ActionResult(handled=False, message="")

        if not route.requires_confirmation:
            execution = self._execute_route(route=route, user_id=user_id)
            self._activity.create(
                user_id=user_id,
                event_type=ActivityEventType.INTEGRATION_ACTION_EXECUTED,
                entity_type=ActivityEntityType.INTEGRATION_ACTION,
                entity_id=secrets.token_hex(8),
                summary=f"Выполнено действие {route.tool}.{route.operation}",
                meta={
                    "tool": route.tool,
                    "operation": route.operation,
                    "arg_keys": sorted(list(route.args.keys())),
                    "has_sensitive_content": False,
                },
            )
            self._session.commit()
            return ActionResult(handled=True, message=execution)

        action_id = secrets.token_hex(8)
        self._pending_store[action_id] = PendingAction(
            id=action_id,
            user_id=user_id,
            session_id=session_id,
            tool=route.tool,
            operation=route.operation,
            args=route.args,
            created_at=self._now(),
        )
        summary = f"{route.tool}.{route.operation}"
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

        execution = self._execute(
            tool=pending.tool,
            operation=pending.operation,
            args=pending.args,
            user_id=user_id,
        )
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
            message=execution,
        )

    def _parse_message(self, message: str) -> ParsedRoute | None:
        text = message.strip()
        if text.lower().startswith("/tool "):
            return self._parse_tool_command(text[len("/tool ") :].strip())
        return self._parse_intent_text(text)

    @staticmethod
    def _parse_tool_command(command: str) -> ParsedRoute | None:
        parts = command.split()
        if len(parts) < 2:
            return None
        tool, operation = parts[0].lower(), parts[1].lower()
        query = " ".join(parts[2:])
        if tool == "calendar" and operation in {"list", "create"}:
            return ParsedRoute(tool=tool, operation=operation, args={"query": query}, requires_confirmation=operation == "create")
        if tool == "todoist" and operation in {"list", "create"}:
            return ParsedRoute(tool=tool, operation=operation, args={"query": query}, requires_confirmation=operation == "create")
        if tool == "linear" and operation == "update":
            return ParsedRoute(tool=tool, operation=operation, args={"query": query}, requires_confirmation=True)
        if tool == "gmail" and operation in {"search", "draft"}:
            return ParsedRoute(tool=tool, operation=operation, args={"query": query}, requires_confirmation=operation == "draft")
        if tool == "github" and operation in {"repos", "issues", "prs", "file"}:
            return ParsedRoute(tool=tool, operation=operation, args={"query": query}, requires_confirmation=False)
        if tool == "bitrix" and operation in {"leads", "deals", "funnel_sum"}:
            return ParsedRoute(tool=tool, operation=operation, args={"query": query}, requires_confirmation=False)
        if tool == "storage" and operation in {"search", "read", "save"}:
            return ParsedRoute(tool=tool, operation=operation, args={"query": query}, requires_confirmation=operation == "save")
        if tool == "imap" and operation in {"search", "read"}:
            return ParsedRoute(tool=tool, operation=operation, args={"query": query}, requires_confirmation=False)
        if tool == "document" and operation == "template_fill":
            return ParsedRoute(tool=tool, operation=operation, args={"query": query}, requires_confirmation=False)
        if tool == "briefing" and operation == "generate":
            return ParsedRoute(tool=tool, operation=operation, args={"query": query}, requires_confirmation=False)
        if tool == "rollback" and operation in {"preview", "execute"}:
            return ParsedRoute(tool=tool, operation=operation, args={"query": query}, requires_confirmation=operation == "execute")
        return None

    @staticmethod
    def _parse_intent_text(message: str) -> ParsedRoute | None:
        lowered = message.lower()
        if "что нового" in lowered and "pr" in lowered:
            return ParsedRoute(tool="github", operation="prs", args={"query": message}, requires_confirmation=False)
        if "сколько денег" in lowered and "воронк" in lowered:
            return ParsedRoute(tool="bitrix", operation="funnel_sum", args={"query": message}, requires_confirmation=False)
        if "найди файл" in lowered and "яндекс" in lowered:
            return ParsedRoute(tool="storage", operation="search", args={"provider": "yandex_disk", "query": message}, requires_confirmation=False)
        if "гарантийный талон" in lowered:
            return ParsedRoute(tool="document", operation="template_fill", args={"template": "warranty_card", "query": message}, requires_confirmation=False)
        if "вечерний итог" in lowered or "сгенерируй итог" in lowered:
            return ParsedRoute(tool="briefing", operation="generate", args={"type": "evening", "query": message}, requires_confirmation=False)
        if "откати последнее действие" in lowered:
            return ParsedRoute(tool="rollback", operation="preview", args={"target": "last_action"}, requires_confirmation=False)
        rollback_execute_match = re.search(r"/rollback\s+execute\s+(\S+)", lowered)
        if rollback_execute_match:
            return ParsedRoute(
                tool="rollback",
                operation="execute",
                args={"action_id": rollback_execute_match.group(1)},
                requires_confirmation=True,
            )
        return None

    def _execute_route(self, *, route: ParsedRoute, user_id: str) -> str:
        return self._execute(tool=route.tool, operation=route.operation, args=route.args, user_id=user_id)

    def _execute(self, *, tool: str, operation: str, args: dict[str, Any], user_id: str) -> str:
        handler = self._tool_handlers.get((tool, operation))
        if handler is None:
            return f"Выполнено действие: {tool}.{operation}"
        result = handler(user_id=user_id, **args)
        if isinstance(result, str):
            return result
        if isinstance(result, dict):
            if "message" in result and isinstance(result["message"], str):
                return result["message"]
            return f"Выполнено действие: {tool}.{operation}. Данные получены."
        return f"Выполнено действие: {tool}.{operation}"

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)
