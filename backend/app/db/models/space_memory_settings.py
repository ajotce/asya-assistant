from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.common import TimestampMixin


class SpaceMemorySettings(Base, TimestampMixin):
    __tablename__ = "space_memory_settings"

    space_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("spaces.id", ondelete="CASCADE"),
        primary_key=True,
    )
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    memory_read_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    memory_write_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    behavior_rules_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    personality_overlay_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
