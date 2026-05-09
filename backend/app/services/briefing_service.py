from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models.common import (
    ActivityEntityType,
    ActivityEventType,
    BriefingKind,
    IntegrationConnectionStatus,
    IntegrationProvider,
)
from app.db.models.integration_connection import IntegrationConnection
from app.db.models.user import User
from app.integrations.telegram.bot_sender import TelegramBotSender
from app.repositories.activity_log_repository import ActivityLogRepository
from app.repositories.briefing_repository import BriefingRepository
from app.repositories.briefing_settings_repository import BriefingSettingsRepository


@dataclass
class BriefingSettingsPatch:
    timezone: str
    morning_enabled: bool
    evening_enabled: bool
    morning_time: str
    evening_time: str
    channel_in_app: bool
    channel_telegram: bool


class BriefingNotFoundError(ValueError):
    pass


class BriefingService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._settings = get_settings()
        self._repo = BriefingRepository(session)
        self._settings_repo = BriefingSettingsRepository(session)
        self._activity = ActivityLogRepository(session)

    def get_settings(self, user: User):
        return self._settings_repo.get_or_create_default(user.id)

    def patch_settings(self, user: User, patch: BriefingSettingsPatch):
        item = self._settings_repo.get_or_create_default(user.id)
        ZoneInfo(patch.timezone)
        self._validate_time(patch.morning_time)
        self._validate_time(patch.evening_time)
        item.timezone = patch.timezone
        item.morning_enabled = patch.morning_enabled
        item.evening_enabled = patch.evening_enabled
        item.morning_time = patch.morning_time
        item.evening_time = patch.evening_time
        item.channel_in_app = patch.channel_in_app
        item.channel_telegram = patch.channel_telegram
        self._settings_repo.save(item)
        self._session.commit()
        self._session.refresh(item)
        return item

    def list_recent(self, *, user_id: str, days: int = 30, limit: int = 100):
        since = datetime.now(timezone.utc) - timedelta(days=days)
        return self._repo.list_recent_for_user(user_id=user_id, since=since, limit=limit)

    def get_by_id(self, *, user_id: str, briefing_id: str):
        item = self._repo.get_for_user(user_id=user_id, briefing_id=briefing_id)
        if item is None:
            raise BriefingNotFoundError("Брифинг не найден.")
        return item

    def generate(self, *, user_id: str, kind: BriefingKind):
        context_text = self._collect_context(user_id=user_id, kind=kind)
        content = self._generate_markdown(kind=kind, context_text=context_text)

        delivered_via: list[str] = []
        settings = self._settings_repo.get_or_create_default(user_id)

        if settings.channel_in_app:
            delivered_via.append("in_app")
        if settings.channel_telegram:
            delivered_via.extend(self._deliver_telegram(user_id=user_id, content=content))

        item = self._repo.create(user_id=user_id, kind=kind, content=content, delivered_via=delivered_via)

        self._activity.create(
            user_id=user_id,
            event_type=ActivityEventType.BRIEFING_GENERATED,
            entity_type=ActivityEntityType.BRIEFING,
            entity_id=item.id,
            summary=f"Сгенерирован {kind.value} briefing",
            meta={"delivered_via": delivered_via},
        )
        if settings.channel_in_app:
            self._activity.create(
                user_id=user_id,
                event_type=ActivityEventType.NOTIFICATION_CENTER,
                entity_type=ActivityEntityType.BRIEFING,
                entity_id=item.id,
                summary=f"Новый {kind.value} briefing",
                meta={"deeplink": f"/briefings/{item.id}"},
            )

        self._session.commit()
        self._session.refresh(item)
        return item

    def cleanup_old(self, *, days: int = 30) -> int:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        deleted = self._repo.delete_older_than(cutoff=cutoff)
        self._session.commit()
        return deleted

    def run_scheduled(self, now_utc: datetime | None = None) -> int:
        now = now_utc or datetime.now(timezone.utc)
        users = list(self._session.execute(select(User)).scalars())
        created = 0
        for user in users:
            settings = self._settings_repo.get_or_create_default(user.id)
            user_now = now.astimezone(ZoneInfo(settings.timezone))
            current_hm = user_now.strftime("%H:%M")
            if settings.morning_enabled and current_hm == settings.morning_time:
                self.generate(user_id=user.id, kind=BriefingKind.MORNING)
                created += 1
            if settings.evening_enabled and current_hm == settings.evening_time:
                self.generate(user_id=user.id, kind=BriefingKind.EVENING)
                created += 1
        return created

    def _collect_context(self, *, user_id: str, kind: BriefingKind) -> str:
        connections = list(
            self._session.execute(
                select(IntegrationConnection).where(
                    IntegrationConnection.user_id == user_id,
                    IntegrationConnection.status == IntegrationConnectionStatus.CONNECTED,
                    IntegrationConnection.provider.in_(
                        [
                            IntegrationProvider.GOOGLE_CALENDAR,
                            IntegrationProvider.LINEAR,
                            IntegrationProvider.TODOIST,
                            IntegrationProvider.GMAIL,
                            IntegrationProvider.IMAP,
                        ]
                    ),
                )
            ).scalars()
        )
        connected = [item.provider.value for item in connections]
        return (
            f"kind={kind.value}\n"
            f"connected_integrations={', '.join(connected) if connected else 'none'}\n"
            "notes=Используй только безопасную сводку без секретов."
        )

    def _generate_markdown(self, *, kind: BriefingKind, context_text: str) -> str:
        prompt = (
            f"Составь краткий {kind.value} брифинг на русском языке в markdown. "
            "Структура: Заголовок, 3-6 буллетов по приоритетам, блок 'Что важно сегодня/итоги дня'. "
            "Не придумывай конкретные факты, если их нет в контексте."
        )
        payload = {
            "model": self._settings.default_chat_model,
            "stream": False,
            "messages": [
                {"role": "system", "content": "Ты делаешь персональные брифинги ассистента Asya."},
                {"role": "user", "content": f"{prompt}\n\nКонтекст:\n{context_text}"},
            ],
            "temperature": 0.3,
        }
        try:
            response = httpx.post(
                f"{self._settings.vsellm_base_url.rstrip('/')}/chat/completions",
                json=payload,
                headers={"Authorization": f"Bearer {self._settings.vsellm_api_key.strip()}"},
                timeout=httpx.Timeout(timeout=60.0, connect=10.0),
            )
            if response.status_code >= 400:
                raise RuntimeError("llm_error")
            data = response.json()
            choices = data.get("choices")
            if isinstance(choices, list) and choices:
                message = choices[0].get("message") if isinstance(choices[0], dict) else None
                if isinstance(message, dict) and isinstance(message.get("content"), str) and message["content"].strip():
                    return message["content"].strip()
            raise RuntimeError("empty_response")
        except Exception:
            title = "Утренний брифинг" if kind == BriefingKind.MORNING else "Вечерний брифинг"
            return (
                f"## {title}\n\n"
                "- Подключенные интеграции обработаны в безопасном режиме.\n"
                "- Новые критичные сигналы отсутствуют.\n"
                "- Проверьте календарь и задачи в связанных системах.\n"
                "\n"
                "### Фокус\n"
                "- Держите приоритет на задачах с ближайшими дедлайнами."
            )

    def _deliver_telegram(self, *, user_id: str, content: str) -> list[str]:
        sender = TelegramBotSender(self._session, self._settings)
        sent = sender.send_notification(user_id=user_id, text=content, parse_mode="Markdown")
        if not sent:
            return []
        return ["telegram"]

    @staticmethod
    def _validate_time(value: str) -> None:
        datetime.strptime(value, "%H:%M")
