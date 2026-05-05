from __future__ import annotations

import logging

import httpx
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.repositories.telegram_account_link_repository import TelegramAccountLinkRepository

logger = logging.getLogger(__name__)


class TelegramBotSender:
    def __init__(self, session: Session, settings: Settings) -> None:
        self._session = session
        self._settings = settings
        self._links = TelegramAccountLinkRepository(session)

    def send_notification(
        self,
        *,
        user_id: str,
        text: str,
        button_text: str | None = None,
        button_url: str | None = None,
    ) -> bool:
        link = self._links.get_active_by_user_id(user_id)
        if link is None:
            return False
        safe_text = text.strip()[:1000]
        if not safe_text:
            return False
        token = self._settings.telegram_bot_token.strip()
        if not token:
            return False
        try:
            payload: dict[str, object] = {"chat_id": int(link.telegram_chat_id), "text": safe_text}
            if button_text and button_url:
                payload["reply_markup"] = {
                    "inline_keyboard": [[{"text": button_text[:64], "url": button_url[:1024]}]],
                }
            httpx.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json=payload,
                timeout=httpx.Timeout(timeout=10.0, connect=3.0),
            )
            return True
        except Exception:
            logger.exception("telegram_send_failed user_id=%s", user_id)
            return False
