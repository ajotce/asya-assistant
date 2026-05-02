from __future__ import annotations

from typing import Optional

from sqlalchemy import Enum as SAEnum, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.common import IdMixin, MemoryStatus, TimestampMixin


class MemoryEpisode(Base, IdMixin, TimestampMixin):
    __tablename__ = "memory_episodes"
    __table_args__ = (
        Index("ix_memory_episodes_user_status", "user_id", "status"),
        Index("ix_memory_episodes_user_space", "user_id", "space_id"),
    )

    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    chat_id: Mapped[str] = mapped_column(String(36), ForeignKey("chats.id", ondelete="CASCADE"), nullable=False, index=True)
    space_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("spaces.id", ondelete="SET NULL"), nullable=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[MemoryStatus] = mapped_column(
        SAEnum(MemoryStatus, name="memory_status", native_enum=False),
        nullable=False,
        default=MemoryStatus.NEEDS_REVIEW,
    )
    source: Mapped[str] = mapped_column(String(120), nullable=False, default="assistant")
