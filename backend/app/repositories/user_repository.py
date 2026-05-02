from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.common import UserRole, UserStatus
from app.db.models.user import User


class UserRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(self, user_id: str) -> User | None:
        return self._session.get(User, user_id)

    def get_by_email(self, email: str) -> User | None:
        stmt = select(User).where(User.email == email)
        return self._session.execute(stmt).scalar_one_or_none()

    def create(
        self,
        *,
        email: str,
        display_name: str,
        password_hash: Optional[str] = None,
        role: UserRole = UserRole.USER,
        status: UserStatus = UserStatus.PENDING,
    ) -> User:
        user = User(
            email=email,
            display_name=display_name,
            password_hash=password_hash,
            role=role,
            status=status,
        )
        self._session.add(user)
        self._session.flush()
        return user

    def save(self, user: User) -> User:
        self._session.add(user)
        self._session.flush()
        return user
