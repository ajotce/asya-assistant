from __future__ import annotations

import logging

from app.db.models.access_request import AccessRequest
from app.db.models.user import User

logger = logging.getLogger(__name__)


class AccessRequestNotifier:
    def on_submitted(self, request: AccessRequest) -> None:
        raise NotImplementedError

    def on_approved(self, request: AccessRequest, user: User, setup_link: str) -> None:
        raise NotImplementedError

    def on_rejected(self, request: AccessRequest) -> None:
        raise NotImplementedError


class DevLogAccessRequestNotifier(AccessRequestNotifier):
    """Dev-only mock notifier.

    Реальных email/Telegram отправок здесь нет: только структурированный лог.
    """

    def on_submitted(self, request: AccessRequest) -> None:
        logger.info(
            "access_request_submitted id=%s email=%s display_name=%s",
            request.id,
            request.email,
            request.display_name,
        )

    def on_approved(self, request: AccessRequest, user: User, setup_link: str) -> None:
        logger.info(
            "access_request_approved id=%s email=%s user_id=%s setup_link=%s",
            request.id,
            request.email,
            user.id,
            setup_link,
        )

    def on_rejected(self, request: AccessRequest) -> None:
        logger.info(
            "access_request_rejected id=%s email=%s",
            request.id,
            request.email,
        )
