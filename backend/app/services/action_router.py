from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import re
import secrets
from typing import Any

from sqlalchemy.orm import Session

from app.db.models.common import ActivityEntityType, ActivityEventType
from app.integrations.bitrix24 import Bitrix24ConfigurationError, Bitrix24Service
from app.integrations.github import GitHubAccessDeniedError, GitHubNotConnectedError, GitHubService
from app.repositories.user_repository import UserRepository
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
        self._users = UserRepository(session)

    def handle(self, *, user_id: str, session_id: str, message: str) -> ActionResult:
        text = message.strip()
        if not text:
            return ActionResult(handled=False, message="")

        if text.lower().startswith("/confirm "):
            action_id = text.split(" ", 1)[1].strip()
            return self._confirm_action(user_id=user_id, action_id=action_id)

        bitrix_result = self._handle_bitrix24_readonly(user_id=user_id, text=text)
        if bitrix_result is not None:
            return bitrix_result
        github_result = self._handle_github_readonly(user_id=user_id, text=text)
        if github_result is not None:
            return github_result

        if not text.lower().startswith("/tool "):
            return ActionResult(handled=False, message="")

        command = text[len("/tool ") :].strip()
        route = self._parse_command(command)
        if route is None:
            return ActionResult(
                handled=True,
                message=(
                    "Неподдерживаемая tool-команда. Доступно: "
                    "calendar list/create, todoist list/create, linear update, gmail search/draft; "
                    "или естественные фразы для GitHub/Bitrix24 read-only."
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

    def _handle_github_readonly(self, *, user_id: str, text: str) -> ActionResult | None:
        lowered = text.lower()
        user = self._users.get_by_id(user_id)
        if user is None:
            return None
        service = GitHubService(self._session)

        if "что в моих pr" in lowered or "что в моих пулл-реквестах" in lowered:
            try:
                repos = service.list_repositories(user=user, per_page=20)
                open_prs: list[str] = []
                for repo in repos[:10]:
                    owner = repo.get("owner", {}).get("login")
                    name = repo.get("name")
                    if not owner or not name:
                        continue
                    pulls = service.list_pull_requests(user=user, owner=str(owner), repo=str(name), per_page=10)
                    for pr in pulls:
                        title = str(pr.get("title", "без названия"))
                        url = str(pr.get("html_url", ""))
                        open_prs.append(f"- {owner}/{name}: {title} {url}".strip())
                        if len(open_prs) >= 10:
                            break
                    if len(open_prs) >= 10:
                        break
            except (GitHubNotConnectedError, GitHubAccessDeniedError) as exc:
                return ActionResult(handled=True, message=str(exc))
            if not open_prs:
                return ActionResult(handled=True, message="Открытых PR по доступным репозиториям не найдено.")
            return ActionResult(handled=True, message="Открытые PR:\n" + "\n".join(open_prs))

        if "покажи открытые issues" in lowered:
            repo_match = re.search(r"в\s+репозитории\s+([a-z0-9_.-]+)/([a-z0-9_.-]+)", lowered, re.IGNORECASE)
            if not repo_match:
                return ActionResult(
                    handled=True,
                    message="Уточни репозиторий: 'покажи открытые issues в репозитории owner/repo'.",
                )
            owner, repo_name = repo_match.group(1), repo_match.group(2)
            try:
                issues = service.list_issues(user=user, owner=owner, repo=repo_name, state="open", per_page=20)
            except (GitHubNotConnectedError, GitHubAccessDeniedError) as exc:
                return ActionResult(handled=True, message=str(exc))
            lines = [f"- #{item.get('number')}: {item.get('title', 'без названия')}" for item in issues[:10]]
            return ActionResult(
                handled=True,
                message=(f"Открытые issues в {owner}/{repo_name}:\n" + "\n".join(lines))
                if lines
                else "Открытых issues нет.",
            )

        file_match = re.search(
            r"прочитай файл\s+(.+?)\s+в\s+репозитории\s+([a-z0-9_.-]+)/([a-z0-9_.-]+)(?:\s+ref\s+([a-z0-9_./-]+))?$",
            lowered,
            re.IGNORECASE,
        )
        if file_match:
            file_path, owner, repo_name, ref = (
                file_match.group(1).strip(),
                file_match.group(2),
                file_match.group(3),
                file_match.group(4),
            )
            try:
                payload = service.read_file(user=user, owner=owner, repo=repo_name, path=file_path, ref=ref)
            except (GitHubNotConnectedError, GitHubAccessDeniedError) as exc:
                return ActionResult(handled=True, message=str(exc))
            encoded = str(payload.get("content", "")).replace("\n", "")
            try:
                import base64

                content = base64.b64decode(encoded).decode("utf-8", errors="replace")
            except Exception:  # noqa: BLE001
                return ActionResult(handled=True, message="Не удалось декодировать содержимое файла.")
            if len(content) > 2000:
                content = content[:2000] + "\n... (обрезано)"
            return ActionResult(handled=True, message=f"Файл {file_path}:\n{content}")

        return None

    def _handle_bitrix24_readonly(self, *, user_id: str, text: str) -> ActionResult | None:
        lowered = text.lower()
        service = Bitrix24Service(self._session)

        source_match = re.search(r"сколько лидов сегодня пришло из источника\s+(.+)\??$", lowered, re.IGNORECASE)
        if source_match:
            source_id = source_match.group(1).strip().upper()
            try:
                payload = service.list_leads(user_id=user_id, source_id=source_id, created_since=self._now().date())
            except Bitrix24ConfigurationError:
                return ActionResult(handled=True, message="Bitrix24 не подключён. Нужна настройка подключения.")
            leads = payload.get("result", [])
            return ActionResult(handled=True, message=f"Сегодня из источника {source_id} пришло лидов: {len(leads)}.")

        money_match = re.search(
            r"сколько денег в воронке\s+(.+)\s+на стадии\s+(.+)\??$",
            lowered,
            re.IGNORECASE,
        )
        if money_match:
            pipeline = money_match.group(1).strip().lower()
            stage = money_match.group(2).strip().lower()
            try:
                payload = service.list_deals(user_id=user_id)
            except Bitrix24ConfigurationError:
                return ActionResult(handled=True, message="Bitrix24 не подключён. Нужна настройка подключения.")
            total = 0.0
            for deal in payload.get("result", []):
                category = str(deal.get("CATEGORY_ID", "")).lower()
                stage_id = str(deal.get("STAGE_ID", "")).lower()
                if pipeline in category and stage in stage_id:
                    try:
                        total += float(deal.get("OPPORTUNITY", 0))
                    except (TypeError, ValueError):
                        continue
            return ActionResult(handled=True, message=f"Сумма в воронке {pipeline} на стадии {stage}: {total:.2f}.")

        period_match = re.search(r"покажи сделки за период\s+(\d{4}-\d{2}-\d{2})\s+(\d{4}-\d{2}-\d{2})", lowered, re.IGNORECASE)
        if period_match:
            date_from = datetime.fromisoformat(period_match.group(1)).date()
            date_to = datetime.fromisoformat(period_match.group(2)).date()
            try:
                payload = service.list_deals(user_id=user_id, date_from=date_from, date_to=date_to)
            except Bitrix24ConfigurationError:
                return ActionResult(handled=True, message="Bitrix24 не подключён. Нужна настройка подключения.")
            deals = payload.get("result", [])
            return ActionResult(
                handled=True,
                message=f"Сделок за период {date_from.isoformat()}..{date_to.isoformat()}: {len(deals)}.",
            )
        return None

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)
