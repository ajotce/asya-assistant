from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.common import IdMixin, TimestampMixin


class DiaryEntry(Base, IdMixin, TimestampMixin):
    __tablename__ = "diary_entries"
    __table_args__ = (
        Index("ix_diary_entries_user_created", "user_id", "created_at"),
    )

    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False, default="Запись дневника")
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    transcript: Mapped[str] = mapped_column(Text, nullable=False, default="")
    topics: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    decisions: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    mentions: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    source_audio_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    processing_status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    processing_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
