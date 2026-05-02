from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone

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
from app.repositories.activity_log_repository import ActivityLogRepository
from app.repositories.integration_connection_repository import IntegrationConnectionRepository
from app.repositories.observation_repository import ObservationRepository
from app.repositories.observation_rule_repository import ObservationRuleRepository
from app.repositories.user_repository import UserRepository
from app.services.notification_center_service import NotificationCenterService


@dataclass
class DetectorResult:
    detector: str
    title: str
    details: str
    severity: ObservationSeverity
    dedup_hint: str
    context_payload: dict


class ObserverService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._users = UserRepository(session)
        self._rules = ObservationRuleRepository(session)
        self._observations = ObservationRepository(session)
        self._activity = ActivityLogRepository(session)
        self._integrations = IntegrationConnectionRepository(session)
        self._notifications = NotificationCenterService(session)

    def run_all_users(self) -> int:
        stmt_users = self._session.query(User).all()
        created = 0
        for user in stmt_users:
            created += self.run_for_user(user)
        self._session.commit()
        return created

    def run_for_user(self, user: User) -> int:
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
        results.extend(self._detect_unanswered_important_email(user))
        results.extend(self._detect_meeting_conflict(user))
        results.extend(self._detect_back_to_back_meetings(user))
        results.extend(self._detect_burnout_pattern(user))
        return results

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

    def _detect_unanswered_important_email(self, user: User) -> list[DetectorResult]:
        if not self._is_connected(user.id, IntegrationProvider.GMAIL):
            return []
        return [
            DetectorResult(
                detector="UnansweredImportantEmail",
                title="Есть важные письма без ответа",
                details="Найдены входящие письма с высоким приоритетом без ответа > 24 часов.",
                severity=ObservationSeverity.CRITICAL,
                dedup_hint="important_email",
                context_payload={"source": ["gmail"]},
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

    @staticmethod
    def _build_dedup_key(result: DetectorResult) -> str:
        raw = f"{result.detector}:{result.dedup_hint}:{result.title}:{result.details}"
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()
