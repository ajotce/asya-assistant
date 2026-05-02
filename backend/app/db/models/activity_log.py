from __future__ import annotations

from typing import Optional

from sqlalchemy import Enum as SAEnum, ForeignKey, Index, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.common import ActivityEntityType, ActivityEventType, IdMixin, TimestampMixin


class ActivityLog(Base, IdMixin, TimestampMixin):
    __tablename__ = "activity_logs"
    __table_args__ = (
        Index("ix_activity_logs_user_created", "user_id", "created_at"),
        Index("ix_activity_logs_user_space", "user_id", "space_id"),
    )

    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    space_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("spaces.id", ondelete="SET NULL"), nullable=True)
    event_type: Mapped[ActivityEventType] = mapped_column(
        SAEnum(ActivityEventType, name="activity_event_type", native_enum=False),
        nullable=False,
    )
    entity_type: Mapped[ActivityEntityType] = mapped_column(
        SAEnum(ActivityEntityType, name="activity_entity_type", native_enum=False),
        nullable=False,
    )
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    meta: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
