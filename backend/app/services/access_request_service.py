from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import secrets

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models.access_request import AccessRequest
from app.db.models.common import AccessRequestStatus, UserStatus
from app.db.models.user import User
from app.repositories.access_request_repository import AccessRequestRepository
from app.repositories.signup_token_repository import SignupTokenRepository
from app.repositories.user_repository import UserRepository
from app.services.access_request_notifier import AccessRequestNotifier, DevLogAccessRequestNotifier
from app.services.chat_service_v2 import ChatServiceV2
from app.services.email_transport import EmailTransport, get_email_transport
from app.services.user_service import UserService


class AccessRequestError(ValueError):
    pass


class AccessRequestNotFoundError(AccessRequestError):
    pass


class SignupTokenError(AccessRequestError):
    pass


class AccessRequestService:
    def __init__(
        self,
        session: Session,
        notifier: AccessRequestNotifier | None = None,
        email_transport: EmailTransport | None = None,
    ) -> None:
        self._session = session
        self._settings = get_settings()
        self._requests = AccessRequestRepository(session)
        self._tokens = SignupTokenRepository(session)
        self._users = UserRepository(session)
        self._user_service = UserService(session)
        self._chat_service = ChatServiceV2(session)
        self._notifier = notifier or DevLogAccessRequestNotifier()
        self._email_transport = email_transport or get_email_transport(self._settings)

    def submit_request(self, *, email: str, display_name: str, reason: str) -> AccessRequest:
        normalized_email = email.strip().lower()
        normalized_name = display_name.strip()
        normalized_reason = reason.strip()

        pending = self._requests.get_pending_by_email(normalized_email)
        if pending is not None:
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

    def approve_request(self, *, request_id: str, admin_user: User) -> tuple[AccessRequest, User, str]:
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
                status=UserStatus.PENDING,
            )
        else:
            if not user.display_name.strip():
                user.display_name = request.display_name
            if not user.password_hash:
                user.status = UserStatus.PENDING
            self._users.save(user)
            self._chat_service.ensure_single_active_base_chat(user.id)
            self._session.commit()
            self._session.refresh(user)

        raw_token = secrets.token_urlsafe(48)
        token_hash = self._hash_token(raw_token)
        expires_at = self._now() + timedelta(hours=self._settings.signup_token_ttl_hours)
        self._tokens.create(
            access_request_id=request.id,
            user_id=user.id,
            email=request.email,
            token_hash=token_hash,
            created_by_user_id=admin_user.id,
            expires_at=expires_at,
        )

        request.status = AccessRequestStatus.APPROVED
        request.approved_by = admin_user.id
        request.reviewed_at = self._now()
        self._requests.save(request)
        self._session.commit()
        self._session.refresh(request)

        setup_link = f"{self._settings.public_base_url.rstrip('/')}/setup-password?token={raw_token}"
        self._notifier.on_approved(request, user, setup_link)
        self._email_transport.send(
            to_email=request.email,
            subject="Asya: доступ одобрен",
            text_body=(
                "Заявка на доступ к Asya одобрена.\n"
                "Это не passwordless-вход: сначала задайте пароль по одноразовой ссылке.\n"
                f"Ссылка: {setup_link}\n"
                f"Срок действия: {self._settings.signup_token_ttl_hours} ч."
            ),
        )
        return request, user, setup_link

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
        self._email_transport.send(
            to_email=request.email,
            subject="Asya: заявка отклонена",
            text_body="К сожалению, в доступе к Asya сейчас отказано. Можно подать новую заявку позже.",
        )
        return request

    def complete_signup_with_token(self, *, raw_token: str, password_hash: str) -> User:
        token = self._tokens.get_active_by_hash(self._hash_token(raw_token), now=self._now())
        if token is None:
            raise SignupTokenError("Ссылка недействительна или уже использована.")
        user = self._users.get_by_email(token.email)
        if user is None:
            raise SignupTokenError("Пользователь для ссылки не найден.")

        user.password_hash = password_hash
        user.status = UserStatus.ACTIVE
        self._users.save(user)

        token.used_at = self._now()
        self._tokens.save(token)

        self._session.commit()
        self._session.refresh(user)
        return user

    @staticmethod
    def _now() -> datetime:
        return datetime.now(tz=timezone.utc)

    def _hash_token(self, raw_token: str) -> str:
        key = self._settings.auth_session_hash_secret.encode("utf-8")
        return hmac.new(key=key, msg=raw_token.encode("utf-8"), digestmod=hashlib.sha256).hexdigest()
