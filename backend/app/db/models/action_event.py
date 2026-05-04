from __future__ import annotations

from typing import Optional

from sqlalchemy import Boolean, DateTime, Enum as SAEnum, ForeignKey, Index, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.common import IdMixin, RollbackStatus, TimestampMixin


class ActionEvent(Base, IdMixin, TimestampMixin):
    __tablename__ = "action_events"
    __table_args__ = (
        Index("ix_action_events_user_created", "user_id", "created_at"),
        Index("ix_action_events_user_reversible", "user_id", "reversible"),
    )

    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    activity_log_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("activity_logs.id", ondelete="SET NULL"), nullable=True)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    operation: Mapped[str] = mapped_column(String(64), nullable=False)
    target_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    reversible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    rollback_status: Mapped[RollbackStatus] = mapped_column(
        SAEnum(RollbackStatus, name="rollback_status", native_enum=False),
        nullable=False,
        default=RollbackStatus.NOT_REQUESTED,
    )
    rollback_strategy: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    rollback_deadline: Mapped[Optional[str]] = mapped_column(DateTime(timezone=True), nullable=True)
    previous_state: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    safe_metadata: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    rollback_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
