from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.db.models.access_request import AccessRequest
from app.db.models.common import AccessRequestStatus, UserStatus
from app.db.models.user import User
from app.repositories.access_request_repository import AccessRequestRepository
from app.repositories.user_repository import UserRepository
from app.services.access_request_notifier import AccessRequestNotifier, DevLogAccessRequestNotifier
from app.services.chat_service_v2 import ChatServiceV2
from app.services.user_service import UserService


class AccessRequestError(ValueError):
    pass


class AccessRequestNotFoundError(AccessRequestError):
    pass


class AccessRequestService:
    def __init__(self, session: Session, notifier: AccessRequestNotifier | None = None) -> None:
        self._session = session
        self._requests = AccessRequestRepository(session)
        self._users = UserRepository(session)
        self._user_service = UserService(session)
        self._chat_service = ChatServiceV2(session)
        self._notifier = notifier or DevLogAccessRequestNotifier()

    def submit_request(self, *, email: str, display_name: str, reason: str) -> AccessRequest:
        normalized_email = email.strip().lower()
        normalized_name = display_name.strip()
        normalized_reason = reason.strip()

        pending = self._requests.get_pending_by_email(normalized_email)
        if pending is not None:
            # Предсказуемое поведение: повторный submit на pending-email возвращает существующую заявку.
            return pending

        request = self._requests.create(
            email=normalized_email,
            display_name=normalized_name,
            reason=normalized_reason,
        )
        self._session.commit()
        self._session.refresh(request)
        self._notifier.on_submitted(request)
        return request

    def list_requests(self) -> list[AccessRequest]:
        return self._requests.list_requests()

    def approve_request(self, *, request_id: str, admin_user: User) -> tuple[AccessRequest, User]:
        request = self._requests.get_by_id(request_id)
        if request is None:
            raise AccessRequestNotFoundError("Заявка не найдена.")
        if request.status != AccessRequestStatus.PENDING:
            raise AccessRequestError("Обрабатывать можно только pending-заявки.")
        if admin_user.email.lower() == request.email.lower():
            raise AccessRequestError("Админ не может аппрувить свою собственную заявку.")

        user = self._users.get_by_email(request.email)
        if user is None:
            user = self._user_service.create_user(
                email=request.email,
                display_name=request.display_name,
                password_hash=None,
                status=UserStatus.ACTIVE,
            )
        else:
            user.status = UserStatus.ACTIVE
            if not user.display_name.strip():
                user.display_name = request.display_name
            self._users.save(user)
            self._chat_service.ensure_single_active_base_chat(user.id)
            self._session.commit()
            self._session.refresh(user)

        request.status = AccessRequestStatus.APPROVED
        request.approved_by = admin_user.id
        request.reviewed_at = self._now()
        self._requests.save(request)
        self._session.commit()
        self._session.refresh(request)
        self._notifier.on_approved(request, user)
        return request, user

    def reject_request(self, *, request_id: str, admin_user: User) -> AccessRequest:
        request = self._requests.get_by_id(request_id)
        if request is None:
            raise AccessRequestNotFoundError("Заявка не найдена.")
        if request.status != AccessRequestStatus.PENDING:
            raise AccessRequestError("Обрабатывать можно только pending-заявки.")
        if admin_user.email.lower() == request.email.lower():
            raise AccessRequestError("Админ не может отклонять свою собственную заявку.")

        request.status = AccessRequestStatus.REJECTED
        request.approved_by = admin_user.id
        request.reviewed_at = self._now()
        self._requests.save(request)
        self._session.commit()
        self._session.refresh(request)
        self._notifier.on_rejected(request)
        return request

    @staticmethod
    def _now() -> datetime:
        return datetime.now(tz=timezone.utc)
