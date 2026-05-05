from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
import json
import re
import secrets
from typing import Any, Callable

from sqlalchemy.orm import Session

from app.db.models.common import ActivityEntityType, ActivityEventType
from app.integrations.bitrix24 import Bitrix24Service
from app.repositories.action_event_repository import ActionEventRepository
from app.repositories.activity_log_repository import ActivityLogRepository
from app.repositories.document_template_repository import DocumentTemplateRepository
from app.services.document_fill_service import DocumentFillService
from app.services.file_storage_service import FileStorageService


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
        self._action_events = ActionEventRepository(session)
        self._tool_handlers = tool_handlers or {}

    def handle(self, *, user_id: str, session_id: str, message: str) -> ActionResult:
        text = message.strip()
        if not text:
            return ActionResult(handled=False, message="")

        pending_fill = self._find_pending_document_fill(user_id=user_id)
        if (
            pending_fill is not None
            and not text.lower().startswith("/confirm ")
            and not text.lower().startswith("/tool ")
        ):
            result = self._handle_document_fill(
                user_id=user_id,
                session_id=session_id,
                message=text,
                pending=pending_fill,
            )
            if result.handled:
                return result

        if text.lower().startswith("/confirm "):
            action_id = text.split(" ", 1)[1].strip()
            return self._confirm_action(user_id=user_id, action_id=action_id)

        doc_fill_result = self._handle_document_fill(
            user_id=user_id,
            session_id=session_id,
            message=text,
            pending=None,
        )
        if doc_fill_result.handled:
            return doc_fill_result

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
        activity = self._activity.create(
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
        rollback_meta = self._build_rollback_meta(pending)
        self._action_events.create(
            user_id=user_id,
            activity_log_id=activity.id,
            provider=rollback_meta["provider"],
            operation=pending.operation,
            target_id=rollback_meta["target_id"],
            reversible=rollback_meta["reversible"],
            rollback_strategy=rollback_meta["rollback_strategy"],
            rollback_deadline=None,
            previous_state=rollback_meta["previous_state"],
            safe_metadata={**rollback_meta["metadata"], "activity_log_id": activity.id},
            rollback_notes=rollback_meta["rollback_notes"],
        )
        self._session.commit()
        return ActionResult(handled=True, message=execution)

    def _parse_message(self, message: str) -> ParsedRoute | None:
        text = message.strip()
        if text.lower().startswith("/tool "):
            return self._parse_tool_command(text[len("/tool ") :].strip())

        storage_route = self._parse_natural_storage_command(text)
        if storage_route is not None:
            return storage_route

        return self._parse_intent_text(text)

    @staticmethod
    def _parse_tool_command(command: str) -> ParsedRoute | None:
        parts = command.split()
        if len(parts) < 2:
            return None
        tool, operation = parts[0].lower(), parts[1].lower()
        query = " ".join(parts[2:])

        if tool == "calendar" and operation in {"list", "create", "update"}:
            return ActionRouter._parse_tool_args(
                tool,
                operation,
                parts[2:],
                requires_confirmation=operation in {"create", "update"},
            )
        if tool == "todoist" and operation in {"list", "create", "update"}:
            return ActionRouter._parse_tool_args(
                tool,
                operation,
                parts[2:],
                requires_confirmation=operation in {"create", "update"},
            )
        if tool == "linear" and operation == "update":
            return ActionRouter._parse_tool_args(
                tool,
                operation,
                parts[2:],
                requires_confirmation=True,
            )
        if tool == "gmail" and operation in {"search", "draft"}:
            return ActionRouter._parse_tool_args(
                tool,
                operation,
                parts[2:],
                requires_confirmation=operation == "draft",
            )
        if tool in {"drive", "yandex", "onedrive"} and operation in {"create", "search"}:
            return ActionRouter._parse_tool_args(
                tool,
                operation,
                parts[2:],
                requires_confirmation=operation == "create",
            )
        if tool in {"memory", "rules", "personality"} and operation == "update":
            return ActionRouter._parse_tool_args(
                tool,
                operation,
                parts[2:],
                requires_confirmation=True,
            )
        if tool == "github" and operation in {"repos", "issues", "prs", "file"}:
            return ParsedRoute(
                tool=tool,
                operation=operation,
                args={"query": query},
                requires_confirmation=False,
            )
        if tool == "bitrix" and operation in {"leads", "deals", "funnel_sum"}:
            return ParsedRoute(
                tool=tool,
                operation=operation,
                args={"query": query},
                requires_confirmation=False,
            )
        if tool == "storage" and operation in {"search", "read", "save"}:
            return ParsedRoute(
                tool=tool,
                operation=operation,
                args={"query": query},
                requires_confirmation=operation == "save",
            )
        if tool == "imap" and operation in {"search", "read"}:
            return ParsedRoute(
                tool=tool,
                operation=operation,
                args={"query": query},
                requires_confirmation=False,
            )
        if tool == "document" and operation == "template_fill":
            return ParsedRoute(
                tool=tool,
                operation=operation,
                args={"query": query},
                requires_confirmation=False,
            )
        if tool == "briefing" and operation == "generate":
            return ParsedRoute(
                tool=tool,
                operation=operation,
                args={"query": query},
                requires_confirmation=False,
            )
        if tool == "rollback" and operation in {"preview", "execute"}:
            return ParsedRoute(
                tool=tool,
                operation=operation,
                args={"query": query},
                requires_confirmation=operation == "execute",
            )
        return None

    @staticmethod
    def _parse_intent_text(message: str) -> ParsedRoute | None:
        lowered = message.lower()

        if "сколько лидов" in lowered:
            return ParsedRoute(
                tool="bitrix",
                operation="leads",
                args={
                    "source_id": ActionRouter._extract_source_id(message),
                    "created_since": date.today() if "сегодня" in lowered else None,
                    "query": message,
                },
                requires_confirmation=False,
            )
        if "покажи сделки" in lowered:
            date_from, date_to = ActionRouter._extract_date_range(message)
            return ParsedRoute(
                tool="bitrix",
                operation="deals",
                args={"date_from": date_from, "date_to": date_to, "query": message},
                requires_confirmation=False,
            )
        if "что нового" in lowered and "pr" in lowered:
            return ParsedRoute(
                tool="github",
                operation="prs",
                args={"query": message},
                requires_confirmation=False,
            )
        if "сколько денег" in lowered and "воронк" in lowered:
            return ParsedRoute(
                tool="bitrix",
                operation="funnel_sum",
                args={"query": message},
                requires_confirmation=False,
            )
        if "найди файл" in lowered and "яндекс" in lowered:
            return ParsedRoute(
                tool="storage",
                operation="search",
                args={"provider": "yandex_disk", "query": message},
                requires_confirmation=False,
            )
        if "гарантийный талон" in lowered:
            return ParsedRoute(
                tool="document",
                operation="template_fill",
                args={"template": "warranty_card", "query": message},
                requires_confirmation=False,
            )
        if "вечерний итог" in lowered or "сгенерируй итог" in lowered:
            return ParsedRoute(
                tool="briefing",
                operation="generate",
                args={"type": "evening", "query": message},
                requires_confirmation=False,
            )
        if "откати последнее действие" in lowered:
            return ParsedRoute(
                tool="rollback",
                operation="preview",
                args={"target": "last_action"},
                requires_confirmation=False,
            )
        rollback_execute_match = re.search(r"/rollback\s+execute\s+(\S+)", lowered)
        if rollback_execute_match:
            return ParsedRoute(
                tool="rollback",
                operation="execute",
                args={"action_id": rollback_execute_match.group(1)},
                requires_confirmation=True,
            )
        return None

    @staticmethod
    def _parse_natural_storage_command(message: str) -> ParsedRoute | None:
        lower = message.strip().lower()
        if "найди документ" in lower and "моих файлах" in lower:
            return ParsedRoute(
                tool="drive",
                operation="search",
                args={"query": message.strip()},
                requires_confirmation=True,
            )
        if "сохрани файл" not in lower:
            return None

        provider = "drive"
        if "onedrive" in lower or "one drive" in lower:
            provider = "onedrive"
        elif "yandex" in lower or "яндекс" in lower:
            provider = "yandex"

        return ParsedRoute(
            tool=provider,
            operation="create",
            args={"query": message.strip()},
            requires_confirmation=True,
        )

    @staticmethod
    def _parse_tool_args(
        tool: str,
        operation: str,
        tokens: list[str],
        *,
        requires_confirmation: bool,
    ) -> ParsedRoute:
        args: dict[str, Any] = {"query": " ".join(tokens)}
        key_values: dict[str, str] = {}
        for token in tokens:
            if "=" in token:
                key, value = token.split("=", 1)
                key_values[key.strip()] = value.strip()
        if "target_id" in key_values:
            args["target_id"] = key_values["target_id"]
        if "previous_state" in key_values:
            try:
                args["previous_state"] = json.loads(key_values["previous_state"])
            except json.JSONDecodeError:
                args["previous_state"] = None
        return ParsedRoute(
            tool=tool,
            operation=operation,
            args=args,
            requires_confirmation=requires_confirmation,
        )

    def _execute_route(self, *, route: ParsedRoute, user_id: str) -> str:
        return self._execute(tool=route.tool, operation=route.operation, args=route.args, user_id=user_id)

    def _execute(self, *, tool: str, operation: str, args: dict[str, Any], user_id: str) -> str:
        handler = self._tool_handlers.get((tool, operation))
        if handler is not None:
            result = handler(user_id=user_id, **args)
            return self._format_execution_result(tool=tool, operation=operation, result=result)

        if tool == "bitrix" and operation in {"leads", "deals"}:
            return self._execute_bitrix_read(operation=operation, args=args, user_id=user_id)

        return f"Выполнено действие: {tool}.{operation}"

    def _execute_bitrix_read(self, *, operation: str, args: dict[str, Any], user_id: str) -> str:
        service = Bitrix24Service(self._session)
        if operation == "leads":
            result = service.list_leads(
                user_id=user_id,
                source_id=args.get("source_id"),
                created_since=args.get("created_since"),
            )
            total = self._extract_total(result)
            return f"Найдено лидов: {total}"
        if operation == "deals":
            result = service.list_deals(
                user_id=user_id,
                date_from=args.get("date_from"),
                date_to=args.get("date_to"),
            )
            total = self._extract_total(result)
            return f"Найдено сделок: {total}"
        return f"Выполнено действие: bitrix.{operation}"

    @staticmethod
    def _format_execution_result(*, tool: str, operation: str, result: Any) -> str:
        if isinstance(result, str):
            return result
        if isinstance(result, dict):
            if "message" in result and isinstance(result["message"], str):
                return result["message"]
            return f"Выполнено действие: {tool}.{operation}. Данные получены."
        return f"Выполнено действие: {tool}.{operation}"

    def _handle_document_fill(
        self,
        *,
        user_id: str,
        session_id: str,
        message: str,
        pending: PendingAction | None,
    ) -> ActionResult:
        if pending is None and "заполни шаблон" not in message.lower():
            return ActionResult(handled=False, message="")

        repo = DocumentTemplateRepository(self._session)
        templates = repo.list_for_user(user_id=user_id)
        if not templates:
            return ActionResult(handled=True, message="У вас пока нет шаблонов документов.")

        template = None
        if pending is not None:
            template = repo.get_for_user(
                template_id=str(pending.args.get("template_id", "")),
                user_id=user_id,
            )
        if template is None:
            template = self._match_template(templates=templates, message=message)
        if template is None:
            if len(templates) == 1:
                template = templates[0]
            else:
                available = ", ".join(item.name for item in templates[:5])
                return ActionResult(
                    handled=True,
                    message=f"Не удалось определить шаблон. Уточните название. Доступные: {available}.",
                )

        values = dict(pending.args.get("values", {})) if pending is not None else {}
        values.update(self._extract_kv_values(message))

        storage = FileStorageService(self._session, user_id=user_id)
        template_bytes = storage.read(provider=template.provider, item_id=template.file_id)
        filler = DocumentFillService()
        preview = filler.preview(
            template_fields=template.fields or [],
            values=values,
            template_bytes=template_bytes,
        )
        if not preview.ok:
            action_id = secrets.token_hex(8)
            self._pending_store[action_id] = PendingAction(
                id=action_id,
                user_id=user_id,
                session_id=session_id,
                tool="document_template",
                operation="fill_collect",
                args={"template_id": template.id, "values": values, "missing": preview.missing_fields},
                created_at=self._now(),
            )
            missing = ", ".join(preview.missing_fields) if preview.missing_fields else "—"
            invalid = ", ".join(f"{k}: {v}" for k, v in preview.invalid_fields.items()) or "—"
            return ActionResult(
                handled=True,
                message=(
                    f"Для шаблона '{template.name}' не хватает данных.\n"
                    f"Missing fields: {missing}\n"
                    f"Invalid fields: {invalid}\n"
                    "Пришлите значения в формате key=value, например: vin=XW8ZZZ1BZGG123456"
                ),
                pending_action_id=action_id,
            )

        artifact = filler.fill(
            template_fields=template.fields or [],
            values=values,
            template_bytes=template_bytes,
            output_filename=str((template.output_settings or {}).get("filename") or template.name),
            user_id=user_id,
        )
        if pending is not None:
            self._pending_store.pop(pending.id, None)
        return ActionResult(
            handled=True,
            message=f"Шаблон '{template.name}' заполнен. DOCX сохранён во временное хранилище: {artifact.path}",
        )

    def _find_pending_document_fill(self, *, user_id: str) -> PendingAction | None:
        for item in self._pending_store.values():
            if (
                item.user_id == user_id
                and item.tool == "document_template"
                and item.operation == "fill_collect"
            ):
                return item
        return None

    @staticmethod
    def _extract_kv_values(message: str) -> dict[str, str]:
        pairs = re.findall(r"([a-zA-Z0-9_]+)\s*[:=]\s*([^,\n;]+)", message)
        return {key.strip(): value.strip() for key, value in pairs}

    @staticmethod
    def _match_template(*, templates: list[Any], message: str):
        lowered = message.lower()
        ordered = sorted(templates, key=lambda item: len(item.name), reverse=True)
        for item in ordered:
            if item.name.lower() in lowered:
                return item
        return None

    @staticmethod
    def _extract_source_id(message: str) -> str | None:
        match = re.search(r"источника?\s+([a-zA-Z0-9_-]+)", message, flags=re.IGNORECASE)
        return match.group(1) if match else None

    @staticmethod
    def _extract_date_range(message: str) -> tuple[date | None, date | None]:
        values = re.findall(r"\d{4}-\d{2}-\d{2}", message)
        date_from = date.fromisoformat(values[0]) if len(values) >= 1 else None
        date_to = date.fromisoformat(values[1]) if len(values) >= 2 else None
        return date_from, date_to

    @staticmethod
    def _extract_total(result: dict[str, Any]) -> int:
        raw_total = result.get("total")
        if isinstance(raw_total, int):
            return raw_total
        items = result.get("result")
        if isinstance(items, list):
            return len(items)
        return 0

    @staticmethod
    def _build_rollback_meta(pending: PendingAction) -> dict[str, Any]:
        provider_map = {
            "calendar": "google_calendar",
            "todoist": "todoist",
            "linear": "linear",
            "gmail": "gmail",
            "drive": "google_drive",
            "yandex": "yandex_disk",
            "onedrive": "onedrive",
            "memory": "memory",
            "rules": "rules",
            "personality": "personality",
            "storage": str(pending.args.get("provider") or "storage"),
        }
        provider = provider_map.get(pending.tool, pending.tool)
        previous_state = pending.args.get("previous_state")
        target_id = pending.args.get("target_id")

        reversible = False
        rollback_strategy: str | None = None
        rollback_notes = "Недостаточно данных для безопасного отката."

        if provider == "todoist" and pending.operation == "create":
            reversible = bool(target_id)
            rollback_strategy = "todoist_create_delete_or_close"
            rollback_notes = None if reversible else "Нет target_id для отката create."
        elif provider == "todoist" and pending.operation == "update":
            reversible = bool(target_id and isinstance(previous_state, dict))
            rollback_strategy = "todoist_update_restore_fields"
            rollback_notes = None if reversible else "Нет previous_state для отката update."
        elif provider == "linear" and pending.operation == "update":
            reversible = bool(target_id and isinstance(previous_state, dict))
            rollback_strategy = "linear_update_restore_fields"
            rollback_notes = None if reversible else "Нет previous_state для отката Linear update."
        elif provider == "google_calendar" and pending.operation == "create":
            reversible = bool(target_id)
            rollback_strategy = "calendar_create_delete_event"
            rollback_notes = None if reversible else "Нет target_id события для отката create."
        elif provider == "google_calendar" and pending.operation == "update":
            reversible = bool(target_id and isinstance(previous_state, dict))
            rollback_strategy = "calendar_update_restore_fields"
            rollback_notes = None if reversible else "Нет previous_state для отката calendar update."
        elif provider in {"google_drive", "yandex_disk", "onedrive"} and pending.operation in {
            "create",
            "save",
        }:
            reversible = bool(target_id)
            rollback_strategy = "drive_create_delete_file_if_safe"
            rollback_notes = None if reversible else "Нет target_id файла для отката create."
        elif provider in {"memory", "rules", "personality"} and pending.operation == "update":
            reversible = bool(target_id)
            rollback_strategy = "memory_version_rollback"
            rollback_notes = None if reversible else "Нет snapshot/version target для rollback."
        elif provider == "gmail":
            rollback_strategy = "irreversible"
            rollback_notes = "Отправленные email и внешние сообщения не откатываются."

        return {
            "provider": provider,
            "target_id": target_id,
            "reversible": reversible,
            "rollback_strategy": rollback_strategy,
            "previous_state": previous_state if isinstance(previous_state, dict) else None,
            "metadata": {
                "tool": pending.tool,
                "operation": pending.operation,
                "arg_keys": sorted(list(pending.args.keys())),
            },
            "rollback_notes": rollback_notes,
        }

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)
