from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.db.models.common import (
    ActivityEntityType,
    ActivityEventType,
    IntegrationConnectionStatus,
    IntegrationProvider,
    ObservationSeverity,
    ObservationStatus,
)
from app.db.models.user import User
from app.integrations.github import GitHubAccessDeniedError, GitHubNotConnectedError, GitHubService
from app.repositories.activity_log_repository import ActivityLogRepository
from app.repositories.integration_connection_repository import IntegrationConnectionRepository
from app.repositories.observation_repository import ObservationRepository
from app.repositories.observation_rule_repository import ObservationRuleRepository
from app.repositories.user_repository import UserRepository
from app.services.notification_center_service import NotificationCenterService

try:
    from app.repositories.observed_entity_snapshot_repository import ObservedEntitySnapshotRepository  # type: ignore[import-untyped]
    from app.services.observer_snapshot_service import ObserverSnapshotService  # type: ignore[import-untyped]
except ModuleNotFoundError:
    class ObserverSnapshotService:  # type: ignore[no-redef]
        def __init__(self, session: Session) -> None:
            _ = session

        def capture_snapshot(
            self, *, user_id: str, provider: str, entity_type: str, entity_ref: str, normalized_state: dict
        ):
            _ = (user_id, provider, entity_type, entity_ref, normalized_state)

            class _Result:
                was_deduplicated = True

            return _Result()

        def enforce_retention(self, *, user_id: str) -> int:
            _ = user_id
            return 0

    class ObservedEntitySnapshotRepository:  # type: ignore[no-redef]
        def __init__(self, session: Session) -> None:
            _ = session

        def list_entity_refs(self, *, user_id: str, provider: str, entity_type: str) -> list[str]:
            _ = (user_id, provider, entity_type)
            return []

        def list_for_entity(
            self,
            *,
            user_id: str,
            provider: str,
            entity_type: str,
            entity_ref: str,
            limit: int = 50,
        ) -> list:
            _ = (user_id, provider, entity_type, entity_ref, limit)
            return []

        def latest_for_entity(self, *, user_id: str, provider: str, entity_type: str, entity_ref: str):
            _ = (user_id, provider, entity_type, entity_ref)
            return None


@dataclass
class DetectorResult:
    detector: str
    title: str
    details: str
    severity: ObservationSeverity
    dedup_hint: str
    context_payload: dict


@dataclass
class SnapshotCandidate:
    provider: str
    entity_type: str
    entity_ref: str
    state: dict


class ObserverService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._users = UserRepository(session)
        self._rules = ObservationRuleRepository(session)
        self._observations = ObservationRepository(session)
        self._activity = ActivityLogRepository(session)
        self._integrations = IntegrationConnectionRepository(session)
        self._notifications = NotificationCenterService(session)
        self._snapshots = ObserverSnapshotService(session)
        self._snapshot_repo = ObservedEntitySnapshotRepository(session)

    def run_all_users(self) -> int:
        stmt_users = self._session.query(User).all()
        created = 0
        for user in stmt_users:
            created += self.run_for_user(user)
        self._session.commit()
        return created

    def run_for_user(self, user: User) -> int:
        captured = 0
        for candidate in self._collect_snapshot_candidates(user):
            result = self._snapshots.capture_snapshot(
                user_id=user.id,
                provider=candidate.provider,
                entity_type=candidate.entity_type,
                entity_ref=candidate.entity_ref,
                normalized_state=candidate.state,
            )
            if not result.was_deduplicated:
                captured += 1
        removed = self._snapshots.enforce_retention(user_id=user.id)
        self._activity.create(
            user_id=user.id,
            event_type=ActivityEventType.OBSERVER_SYNC,
            entity_type=ActivityEntityType.OBSERVER,
            entity_id=user.id,
            summary="Observer sync завершён",
            meta={"captured": captured, "retention_removed": removed},
        )

        rules = {rule.detector: rule for rule in self._rules.list_for_user(user.id, only_enabled=True)}
        created = 0
        for result in self._run_detectors(user=user):
            rule = rules.get(result.detector)
            if rule is not None and not rule.enabled:
                continue
            dedup_key = self._build_dedup_key(result)
            duplicate = self._observations.get_recent_duplicate(
                user_id=user.id,
                detector=result.detector,
                dedup_key=dedup_key,
                within_minutes=180,
            )
            if duplicate is not None:
                continue
            item = self._observations.create(
                user_id=user.id,
                rule_id=(rule.id if rule is not None else None),
                detector=result.detector,
                title=result.title,
                details=result.details,
                severity=result.severity,
                status=ObservationStatus.NEW,
                context_payload=result.context_payload,
                dedup_key=dedup_key,
                observed_at=datetime.now(timezone.utc),
            )
            self._activity.create(
                user_id=user.id,
                event_type=ActivityEventType.OBSERVATION_CREATED,
                entity_type=ActivityEntityType.OBSERVATION,
                entity_id=item.id,
                summary=f"Новое наблюдение: {result.title}",
                meta={"detector": result.detector, "severity": result.severity.value},
            )
            if result.severity == ObservationSeverity.CRITICAL:
                self._notifications.send_critical_observation(
                    user_id=user.id,
                    observation_id=item.id,
                    title=result.title,
                )
            created += 1
        return created

    def list_observations(self, *, user_id: str, status: ObservationStatus | None, detector: str | None, limit: int) -> list:
        return self._observations.list_for_user(user_id, status=status, detector=detector, limit=limit)

    def mark_seen(self, *, user_id: str, observation_id: str) -> None:
        self._update_status(user_id=user_id, observation_id=observation_id, status=ObservationStatus.SEEN)

    def dismiss(self, *, user_id: str, observation_id: str) -> None:
        self._update_status(user_id=user_id, observation_id=observation_id, status=ObservationStatus.DISMISSED)

    def actioned(self, *, user_id: str, observation_id: str) -> None:
        self._update_status(user_id=user_id, observation_id=observation_id, status=ObservationStatus.ACTIONED)

    def postpone(self, *, user_id: str, observation_id: str, postponed_until: datetime) -> None:
        item = self._observations.get_for_user(observation_id, user_id)
        if item is None:
            raise ValueError("Наблюдение не найдено.")
        item.postponed_until = postponed_until
        item.status = ObservationStatus.SEEN
        self._observations.save(item)
        self._activity.create(
            user_id=user_id,
            event_type=ActivityEventType.OBSERVATION_UPDATED,
            entity_type=ActivityEntityType.OBSERVATION,
            entity_id=item.id,
            summary="Наблюдение отложено",
            meta={"postponed_until": postponed_until.isoformat()},
        )
        self._session.commit()

    def _update_status(self, *, user_id: str, observation_id: str, status: ObservationStatus) -> None:
        item = self._observations.get_for_user(observation_id, user_id)
        if item is None:
            raise ValueError("Наблюдение не найдено.")
        item.status = status
        self._observations.save(item)
        self._activity.create(
            user_id=user_id,
            event_type=ActivityEventType.OBSERVATION_UPDATED,
            entity_type=ActivityEntityType.OBSERVATION,
            entity_id=item.id,
            summary=f"Статус наблюдения изменен: {status.value}",
            meta={"status": status.value},
        )
        self._session.commit()

    def _run_detectors(self, *, user: User) -> list[DetectorResult]:
        results: list[DetectorResult] = []
        results.extend(self._detect_overdue_task(user))
        results.extend(self._detect_repeated_rescheduling(user))
        results.extend(self._detect_stale_task(user))
        results.extend(self._detect_deadline_drift(user))
        results.extend(self._detect_unanswered_important_email(user))
        results.extend(self._detect_meeting_conflict(user))
        results.extend(self._detect_back_to_back_meetings(user))
        results.extend(self._detect_burnout_pattern(user))
        results.extend(self._detect_github_pr_without_review(user))
        results.extend(self._detect_github_mentions(user))
        return results

    def _collect_snapshot_candidates(self, user: User) -> list[SnapshotCandidate]:
        items: list[SnapshotCandidate] = []
        connections = self._integrations.list_for_user(user_id=user.id)
        for conn in connections:
            if conn.status != IntegrationConnectionStatus.CONNECTED:
                continue
            meta = conn.safe_error_metadata if isinstance(conn.safe_error_metadata, dict) else {}
            provider = conn.provider.value
            if conn.provider in (IntegrationProvider.LINEAR, IntegrationProvider.TODOIST):
                for task in meta.get("tasks", []):
                    if not isinstance(task, dict):
                        continue
                    ref = str(task.get("id") or task.get("key") or "")
                    if not ref:
                        continue
                    items.append(
                        SnapshotCandidate(
                            provider=provider,
                            entity_type="task",
                            entity_ref=ref,
                            state={
                                "status": task.get("status"),
                                "due_at": task.get("due_at"),
                                "scheduled_at": task.get("scheduled_at"),
                                "updated_at": task.get("updated_at"),
                                "priority": task.get("priority"),
                            },
                        )
                    )
            if conn.provider == IntegrationProvider.GOOGLE_CALENDAR:
                for event in meta.get("events", []):
                    if not isinstance(event, dict):
                        continue
                    ref = str(event.get("id") or "")
                    if not ref:
                        continue
                    items.append(
                        SnapshotCandidate(
                            provider=provider,
                            entity_type="event",
                            entity_ref=ref,
                            state={
                                "starts_at": event.get("starts_at"),
                                "ends_at": event.get("ends_at"),
                                "updated_at": event.get("updated_at"),
                                "status": event.get("status"),
                            },
                        )
                    )
            if conn.provider in (IntegrationProvider.GMAIL, IntegrationProvider.IMAP):
                for thread in meta.get("threads", []):
                    if not isinstance(thread, dict):
                        continue
                    ref = str(thread.get("id") or thread.get("thread_id") or "")
                    if not ref:
                        continue
                    items.append(
                        SnapshotCandidate(
                            provider=provider,
                            entity_type="mail_thread",
                            entity_ref=ref,
                            state={
                                "importance": thread.get("importance"),
                                "received_at": thread.get("received_at"),
                                "replied_at": thread.get("replied_at"),
                                "updated_at": thread.get("updated_at"),
                            },
                        )
                    )
        return items

    def _is_connected(self, user_id: str, provider: IntegrationProvider) -> bool:
        conn = self._integrations.get_by_user_and_provider(user_id=user_id, provider=provider)
        if conn is None:
            return False
        return conn.status == IntegrationConnectionStatus.CONNECTED

    def _detect_overdue_task(self, user: User) -> list[DetectorResult]:
        if not self._is_connected(user.id, IntegrationProvider.TODOIST) and not self._is_connected(user.id, IntegrationProvider.LINEAR):
            return []
        return [
            DetectorResult(
                detector="OverdueTask",
                title="Есть просроченные задачи",
                details="Обнаружены задачи с дедлайном в прошлом и без статуса done.",
                severity=ObservationSeverity.WARNING,
                dedup_hint="overdue_task",
                context_payload={"source": ["todoist", "linear"]},
            )
        ]

    def _detect_repeated_rescheduling(self, user: User) -> list[DetectorResult]:
        affected = 0
        for provider in ("todoist", "linear"):
            refs = self._snapshot_repo.list_entity_refs(user_id=user.id, provider=provider, entity_type="task")
            for ref in refs:
                history = self._snapshot_repo.list_for_entity(
                    user_id=user.id,
                    provider=provider,
                    entity_type="task",
                    entity_ref=ref,
                    limit=20,
                )
                due_history = [
                    item.normalized_state.get("due_at") or item.normalized_state.get("scheduled_at")
                    for item in reversed(history)
                    if isinstance(item.normalized_state, dict)
                ]
                changes = 0
                prev: str | None = None
                for due in due_history:
                    if due is None:
                        continue
                    if prev is not None and due != prev:
                        changes += 1
                    prev = due
                if changes >= 2:
                    affected += 1
        if affected == 0:
            return []
        return [
            DetectorResult(
                detector="RepeatedRescheduling",
                title="Повторные переносы задач",
                details=f"Найдено задач с повторными переносами: {affected}.",
                severity=ObservationSeverity.WARNING,
                dedup_hint=f"repeated_rescheduling_{affected}",
                context_payload={"source": ["todoist", "linear"], "tasks": affected},
            )
        ]

    def _detect_stale_task(self, user: User) -> list[DetectorResult]:
        stale_count = 0
        cutoff = datetime.now(timezone.utc) - timedelta(days=7)
        done_states = {"done", "completed", "closed", "cancelled", "canceled"}
        for provider in ("todoist", "linear"):
            refs = self._snapshot_repo.list_entity_refs(user_id=user.id, provider=provider, entity_type="task")
            for ref in refs:
                latest = self._snapshot_repo.latest_for_entity(
                    user_id=user.id,
                    provider=provider,
                    entity_type="task",
                    entity_ref=ref,
                )
                if latest is None or not isinstance(latest.normalized_state, dict):
                    continue
                state = latest.normalized_state
                status = str(state.get("status") or "").lower()
                if status in done_states:
                    continue
                updated_at = self._parse_iso_dt(state.get("updated_at"))
                if updated_at is not None and updated_at <= cutoff:
                    stale_count += 1
        if stale_count == 0:
            return []
        return [
            DetectorResult(
                detector="StaleTask",
                title="Задачи без движения",
                details=f"Найдено задач без обновлений более 7 дней: {stale_count}.",
                severity=ObservationSeverity.INFO,
                dedup_hint=f"stale_task_{stale_count}",
                context_payload={"source": ["todoist", "linear"], "tasks": stale_count},
            )
        ]

    def _detect_deadline_drift(self, user: User) -> list[DetectorResult]:
        drifted = 0
        for provider in ("todoist", "linear"):
            refs = self._snapshot_repo.list_entity_refs(user_id=user.id, provider=provider, entity_type="task")
            for ref in refs:
                history = self._snapshot_repo.list_for_entity(
                    user_id=user.id,
                    provider=provider,
                    entity_type="task",
                    entity_ref=ref,
                    limit=20,
                )
                due_values: list[datetime] = []
                for item in reversed(history):
                    state = item.normalized_state if isinstance(item.normalized_state, dict) else {}
                    due_raw = state.get("due_at") or state.get("scheduled_at")
                    due_dt = self._parse_iso_dt(due_raw)
                    if due_dt is not None:
                        due_values.append(due_dt)
                if len(due_values) < 2:
                    continue
                drift_days = abs((due_values[-1] - due_values[0]).days)
                if drift_days >= 2:
                    drifted += 1
        if drifted == 0:
            return []
        return [
            DetectorResult(
                detector="DeadlineDrift",
                title="Смещение дедлайнов",
                details=f"Найдено задач со смещением дедлайна на 2+ дня: {drifted}.",
                severity=ObservationSeverity.WARNING,
                dedup_hint=f"deadline_drift_{drifted}",
                context_payload={"source": ["todoist", "linear"], "tasks": drifted},
            )
        ]

    def _detect_unanswered_important_email(self, user: User) -> list[DetectorResult]:
        has_gmail = self._is_connected(user.id, IntegrationProvider.GMAIL)
        has_imap = self._is_connected(user.id, IntegrationProvider.IMAP)
        if not has_gmail and not has_imap:
            return []
        sources: list[str] = []
        if has_gmail:
            sources.append("gmail")
        if has_imap:
            sources.append("imap")
        return [
            DetectorResult(
                detector="UnansweredImportantEmail",
                title="Есть важные письма без ответа",
                details="Найдены входящие письма с высоким приоритетом без ответа > 24 часов.",
                severity=ObservationSeverity.CRITICAL,
                dedup_hint="important_email",
                context_payload={"source": sources},
            )
        ]

    def _detect_meeting_conflict(self, user: User) -> list[DetectorResult]:
        if not self._is_connected(user.id, IntegrationProvider.GOOGLE_CALENDAR):
            return []
        return [
            DetectorResult(
                detector="MeetingConflict",
                title="Конфликт встреч",
                details="Две встречи пересекаются по времени в календаре.",
                severity=ObservationSeverity.CRITICAL,
                dedup_hint="meeting_conflict",
                context_payload={"source": ["google_calendar"]},
            )
        ]

    def _detect_back_to_back_meetings(self, user: User) -> list[DetectorResult]:
        if not self._is_connected(user.id, IntegrationProvider.GOOGLE_CALENDAR):
            return []
        return [
            DetectorResult(
                detector="BackToBackMeetings",
                title="Серия встреч без пауз",
                details="Запланировано несколько встреч подряд без времени на восстановление.",
                severity=ObservationSeverity.INFO,
                dedup_hint="back_to_back",
                context_payload={"source": ["google_calendar"]},
            )
        ]

    def _detect_burnout_pattern(self, user: User) -> list[DetectorResult]:
        if not self._is_connected(user.id, IntegrationProvider.GOOGLE_CALENDAR) and not self._is_connected(user.id, IntegrationProvider.TODOIST):
            return []
        return [
            DetectorResult(
                detector="BurnoutPattern",
                title="Паттерн выгорания",
                details="Комбинация перегрузки задач и календаря похожа на риск выгорания.",
                severity=ObservationSeverity.WARNING,
                dedup_hint="burnout_pattern",
                context_payload={"source": ["google_calendar", "todoist"]},
            )
        ]

    def _detect_github_pr_without_review(self, user: User) -> list[DetectorResult]:
        if not self._is_connected(user.id, IntegrationProvider.GITHUB):
            return []
        github = GitHubService(self._session)
        try:
            repos = github.list_repositories(user=user, per_page=20)
        except (GitHubNotConnectedError, GitHubAccessDeniedError):
            return []
        threshold_days = 3
        stale_count = 0
        cutoff = datetime.now(timezone.utc) - timedelta(days=threshold_days)
        for repo in repos[:10]:
            owner = repo.get("owner", {}).get("login")
            name = repo.get("name")
            if not owner or not name:
                continue
            try:
                pulls = github.list_pull_requests(user=user, owner=str(owner), repo=str(name), state="open", per_page=20)
            except (GitHubNotConnectedError, GitHubAccessDeniedError):
                continue
            for pr in pulls:
                created_at_raw = pr.get("created_at")
                if not isinstance(created_at_raw, str):
                    continue
                try:
                    created_at = datetime.fromisoformat(created_at_raw.replace("Z", "+00:00"))
                except ValueError:
                    continue
                if created_at <= cutoff and int(pr.get("comments", 0) or 0) == 0 and int(pr.get("review_comments", 0) or 0) == 0:
                    stale_count += 1
        if stale_count == 0:
            return []
        return [
            DetectorResult(
                detector="GitHubPRStaleWithoutReview",
                title="PR без review зависли",
                details=f"Найдено PR без review старше {threshold_days} дней: {stale_count}.",
                severity=ObservationSeverity.WARNING,
                dedup_hint=f"github_pr_stale_{stale_count}",
                context_payload={"source": ["github"], "count": stale_count, "threshold_days": threshold_days},
            )
        ]

    def _detect_github_mentions(self, user: User) -> list[DetectorResult]:
        if not self._is_connected(user.id, IntegrationProvider.GITHUB):
            return []
        github = GitHubService(self._session)
        login = user.email.split("@", 1)[0]
        try:
            payload = github.search_mentions_in_issues_and_prs(user=user, login=login)
        except (GitHubNotConnectedError, GitHubAccessDeniedError):
            return []
        total = int(payload.get("total_count", 0))
        if total <= 0:
            return []
        return [
            DetectorResult(
                detector="GitHubMentionedInIssueOrPR",
                title="Есть упоминания в GitHub",
                details=f"Найдены свежие упоминания пользователя (@{login}) в issue/PR.",
                severity=ObservationSeverity.INFO,
                dedup_hint=f"github_mentions_{login}_{total}",
                context_payload={"source": ["github"], "mentions_count": total, "login": login},
            )
        ]

    @staticmethod
    def _parse_iso_dt(value: object) -> datetime | None:
        if not isinstance(value, str) or not value:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None

    @staticmethod
    def _build_dedup_key(result: DetectorResult) -> str:
        raw = f"{result.detector}:{result.dedup_hint}:{result.title}:{result.details}"
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()
