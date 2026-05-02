from __future__ import annotations

from typing import Optional

from sqlalchemy import Enum as SAEnum
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.common import IdMixin, TimestampMixin, UserRole, UserStatus


class User(Base, IdMixin, TimestampMixin):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    password_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    role: Mapped[UserRole] = mapped_column(
        SAEnum(UserRole, name="user_role", native_enum=False),
        nullable=False,
        default=UserRole.USER,
    )
    status: Mapped[UserStatus] = mapped_column(
        SAEnum(UserStatus, name="user_status", native_enum=False),
        nullable=False,
        default=UserStatus.PENDING,
    )
