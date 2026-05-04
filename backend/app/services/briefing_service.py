from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.db.models.common import ActivityEntityType, ActivityEventType
from app.db.models.user import User
from app.integrations.telegram.bot_sender import TelegramBotSender
from app.notifications.notification_center import NotificationCenter
from app.repositories.activity_log_repository import ActivityLogRepository
from app.repositories.briefing_repository import BriefingRepository
from app.repositories.briefing_settings_repository import BriefingSettingsRepository
from app.repositories.diary_entry_repository import DiaryEntryRepository
from app.repositories.diary_settings_repository import DiarySettingsRepository


class BriefingNotFoundError(ValueError):
    pass


@dataclass
class BriefingSettingsPatch:
    morning_enabled: bool
    evening_enabled: bool
    delivery_in_app: bool
    delivery_telegram: bool


class BriefingService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._briefings = BriefingRepository(session)
        self._briefing_settings = BriefingSettingsRepository(session)
        self._diary_settings = DiarySettingsRepository(session)
        self._diary_entries = DiaryEntryRepository(session)
        self._activity = ActivityLogRepository(session)

    def get_settings(self, user: User):
        return self._briefing_settings.get_or_create_default(user.id)

    def patch_settings(self, user: User, patch: BriefingSettingsPatch):
        item = self._briefing_settings.get_or_create_default(user.id)
        item.morning_enabled = patch.morning_enabled
        item.evening_enabled = patch.evening_enabled
        item.delivery_in_app = patch.delivery_in_app
        item.delivery_telegram = patch.delivery_telegram
        self._briefing_settings.save(item)
        self._session.commit()
        self._session.refresh(item)
        return item

    def list_archive(self, user: User, *, limit: int = 20):
        return self._briefings.list_for_user(user.id, limit=limit)

    def get_item(self, user: User, briefing_id: str):
        item = self._briefings.get_for_user(briefing_id, user.id)
        if item is None:
            raise BriefingNotFoundError("Брифинг не найден.")
        return item

    def generate_manual(self, *, user: User, kind: str, app_base_url: str, telegram_sender: TelegramBotSender) -> object:
        settings = self._briefing_settings.get_or_create_default(user.id)
        diary_settings = self._diary_settings.get_or_create_default(user.id)

        content = self._build_markdown(user_id=user.id, kind=kind, include_diary=diary_settings.briefing_enabled)
        title = "Утренний брифинг" if kind == "morning" else "Вечерний итог"

        delivered_telegram = False
        if settings.delivery_telegram:
            delivered_telegram = telegram_sender.send_notification(
                user_id=user.id,
                text=self._telegram_payload(title=title, content=content, app_base_url=app_base_url),
                button_text="Открыть в Asya",
                button_url=app_base_url.rstrip("/") + "/briefings",
            )

        item = self._briefings.create(
            user_id=user.id,
            kind=kind,
            title=title,
            content_markdown=content,
            delivered_in_app=settings.delivery_in_app,
            delivered_telegram=delivered_telegram,
            source_meta={"manual": True, "diary_included": diary_settings.briefing_enabled},
        )

        self._activity.create(
            user_id=user.id,
            event_type=ActivityEventType.NOTIFICATION_CENTER,
            entity_type=ActivityEntityType.NOTIFICATION,
            entity_id=item.id,
            summary=("утренний брифинг готов" if kind == "morning" else "вечерний итог готов"),
            meta={"kind": kind},
        )

        center = NotificationCenter(self._session)
        if settings.delivery_in_app:
            center.notify_user(
                user,
                title=("утренний брифинг готов" if kind == "morning" else "вечерний итог готов"),
                body=title,
                channel="in_app",
                metadata={"briefing_id": item.id, "kind": kind},
            )

        self._session.commit()
        self._session.refresh(item)
        return item

    def _build_markdown(self, *, user_id: str, kind: str, include_diary: bool) -> str:
        recent_activity = self._activity.list_for_user(user_id, limit=5)
        activity_lines = [f"- {row.summary}" for row in recent_activity[:5]]
        if not activity_lines:
            activity_lines = ["- Новых событий нет"]

        diary_lines: list[str]
        if include_diary:
            entries = self._diary_entries.list_for_user(user_id, limit=3)
            diary_lines = [f"- {item.title}" for item in entries] if entries else ["- Новых записей дневника нет"]
        else:
            diary_lines = ["- Раздел дневника отключён в настройках"]

        period_title = "Утро" if kind == "morning" else "Вечер"
        return "\n".join(
            [
                f"# {period_title}",
                "",
                "## Главное",
                *activity_lines,
                "",
                "## Дневник",
                *diary_lines,
            ]
        )

    def _telegram_payload(self, *, title: str, content: str, app_base_url: str) -> str:
        safe_content = content[:3200]
        return f"{title}\n\n{safe_content}\n\nОткрыть в Asya: {app_base_url.rstrip('/')}/briefings"
