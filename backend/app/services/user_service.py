from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from app.db.models.common import UserRole, UserStatus
from app.db.models.user import User
from app.repositories.chat_repository import ChatRepository
from app.repositories.user_repository import UserRepository
from app.services.chat_service_v2 import ChatServiceV2
from app.services.space_service import SpaceService


class UserAlreadyExistsError(ValueError):
    pass


class UserService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._users = UserRepository(session)
        self._chats = ChatRepository(session)
        self._chat_service = ChatServiceV2(session, chat_repository=self._chats)
        self._space_service = SpaceService(session)

    def create_user(
        self,
        *,
        email: str,
        display_name: str,
        password_hash: Optional[str] = None,
        role: UserRole = UserRole.USER,
        status: UserStatus = UserStatus.PENDING,
    ) -> User:
        existing = self._users.get_by_email(email)
        if existing is not None:
            raise UserAlreadyExistsError("Пользователь с таким email уже существует.")

        user = self._users.create(
            email=email,
            display_name=display_name,
            password_hash=password_hash,
            role=role,
            status=status,
        )
        default_space, _ = self._space_service.ensure_default_spaces(user)
        self._chat_service.ensure_single_active_base_chat(user.id, space_id=default_space.id)
        self._session.commit()
        self._session.refresh(user)
        return user

    def get_user(self, user_id: str) -> Optional[User]:
        return self._users.get_by_id(user_id)
