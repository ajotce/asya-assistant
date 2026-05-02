from __future__ import annotations

from typing import Optional

from sqlalchemy import Boolean, Enum as SAEnum, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.common import ChatKind, IdMixin, TimestampMixin


class Chat(Base, IdMixin, TimestampMixin):
    __tablename__ = "chats"
    __table_args__ = (
        Index("ix_chats_user_id_kind", "user_id", "kind"),
        Index("ix_chats_user_id_archived", "user_id", "is_archived"),
        Index("ix_chats_user_id_deleted", "user_id", "is_deleted"),
        Index("ix_chats_user_id_space_id", "user_id", "space_id"),
    )

    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    space_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("spaces.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    kind: Mapped[ChatKind] = mapped_column(
        SAEnum(ChatKind, name="chat_kind", native_enum=False),
        nullable=False,
        default=ChatKind.REGULAR,
    )
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
