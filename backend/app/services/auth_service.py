from __future__ import annotations

from datetime import datetime, timedelta, timezone
import base64
import hashlib
import hmac
import secrets
from typing import Optional

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models.common import UserStatus
from app.db.models.user import User
from app.repositories.auth_session_repository import AuthSessionRepository
from app.repositories.user_repository import UserRepository
from app.services.access_request_service import AccessRequestService
from app.services.chat_service_v2 import ChatServiceV2
from app.services.user_service import UserAlreadyExistsError, UserService


class AuthError(ValueError):
    pass


class RegistrationClosedError(ValueError):
    pass


class AuthService:
    PASSWORD_SCHEME = "pbkdf2_sha256"
    PASSWORD_ITERATIONS = 210_000

    def __init__(self, session: Session) -> None:
        self._session = session
        self._settings = get_settings()
        self._users = UserRepository(session)
        self._auth_sessions = AuthSessionRepository(session)
        self._user_service = UserService(session)
        self._access_requests = AccessRequestService(session)
        self._chat_service = ChatServiceV2(session)

    def register(self, *, email: str, display_name: str, password: str) -> User:
        if self._settings.auth_registration_mode.lower() != "open":
            self._access_requests.submit_request(
                email=email,
                display_name=display_name,
                reason="Автоматическая заявка из закрытой регистрации.",
            )
            raise RegistrationClosedError("Регистрация закрыта, заявка сохранена.")

        password_hash = self._hash_password(password)
        try:
            return self._user_service.create_user(
                email=email,
                display_name=display_name,
                password_hash=password_hash,
                status=UserStatus.ACTIVE,
            )
        except UserAlreadyExistsError as exc:
            raise AuthError(str(exc)) from exc

    def login(self, *, email: str, password: str) -> tuple[User, str, str]:
        user = self._users.get_by_email(email)
        if user is None or user.password_hash is None:
            raise AuthError("Неверный email или пароль.")
        if user.status != UserStatus.ACTIVE:
            raise AuthError("Пользователь не активен.")
        if not self._verify_password(password, user.password_hash):
            raise AuthError("Неверный email или пароль.")
        preferred_chat = self._chat_service.get_preferred_chat(user.id)

        raw_token = self._generate_session_token()
        token_hash = self._hash_session_token(raw_token)
        expires_at = self._now() + timedelta(hours=self._settings.auth_session_ttl_hours)
        self._auth_sessions.create(user_id=user.id, session_token_hash=token_hash, expires_at=expires_at)
        self._session.commit()
        return user, raw_token, preferred_chat.id

    def logout(self, raw_token: Optional[str]) -> None:
        if not raw_token:
            return
        token_hash = self._hash_session_token(raw_token)
        auth_session = self._auth_sessions.get_active_by_token_hash(token_hash, now=self._now())
        if auth_session is None:
            return
        self._auth_sessions.revoke(auth_session, revoked_at=self._now())
        self._session.commit()

    def get_current_user_by_token(self, raw_token: Optional[str]) -> Optional[User]:
        if not raw_token:
            return None
        token_hash = self._hash_session_token(raw_token)
        auth_session = self._auth_sessions.get_active_by_token_hash(token_hash, now=self._now())
        if auth_session is None:
            return None
        user = self._users.get_by_id(auth_session.user_id)
        if user is None or user.status != UserStatus.ACTIVE:
            return None
        return user

    def get_preferred_chat_id(self, user_id: str) -> str:
        return self._chat_service.get_preferred_chat(user_id).id

    @staticmethod
    def _hash_password(password: str) -> str:
        salt = secrets.token_bytes(16)
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            AuthService.PASSWORD_ITERATIONS,
        )
        salt_b64 = base64.b64encode(salt).decode("ascii")
        digest_b64 = base64.b64encode(digest).decode("ascii")
        return f"{AuthService.PASSWORD_SCHEME}${AuthService.PASSWORD_ITERATIONS}${salt_b64}${digest_b64}"

    @staticmethod
    def _verify_password(password: str, password_hash: str) -> bool:
        try:
            scheme, iterations_raw, salt_b64, digest_b64 = password_hash.split("$", 3)
            if scheme != AuthService.PASSWORD_SCHEME:
                return False
            iterations = int(iterations_raw)
            salt = base64.b64decode(salt_b64.encode("ascii"))
            expected = base64.b64decode(digest_b64.encode("ascii"))
        except (ValueError, TypeError):
            return False
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
        return hmac.compare_digest(actual, expected)

    def _hash_session_token(self, raw_token: str) -> str:
        key = self._settings.auth_session_hash_secret.encode("utf-8")
        return hmac.new(key=key, msg=raw_token.encode("utf-8"), digestmod=hashlib.sha256).hexdigest()

    @staticmethod
    def _generate_session_token() -> str:
        return secrets.token_urlsafe(48)

    @staticmethod
    def _now() -> datetime:
        return datetime.now(tz=timezone.utc)
