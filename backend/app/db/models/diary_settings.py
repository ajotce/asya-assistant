from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.common import IdMixin, TimestampMixin


class DiarySettings(Base, IdMixin, TimestampMixin):
    __tablename__ = "diary_settings"

    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    briefing_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    search_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    memories_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    evening_prompt_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
