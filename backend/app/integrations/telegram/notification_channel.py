from __future__ import annotations

import logging

from app.notifications.notification_center import NotificationChannel, NotificationEvent

logger = logging.getLogger(__name__)


class TelegramNotificationChannel(NotificationChannel):
    name = "telegram"

    def __init__(self, bot_sender) -> None:
        self._bot_sender = bot_sender

    def send(self, event: NotificationEvent) -> None:
        safe_title = (event.title or "").strip()[:200]
        safe_body = (event.body or "").strip()[:800]
        if not safe_body:
            return
        message = f"{safe_title}\n\n{safe_body}" if safe_title else safe_body
        try:
            self._bot_sender.send_notification(user_id=event.user_id, text=message)
        except Exception:
            logger.exception("telegram_notification_send_failed user_id=%s", event.user_id)
