from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.common import IdMixin, TimestampMixin


class BriefingSettings(Base, IdMixin, TimestampMixin):
    __tablename__ = "briefing_settings"

    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    morning_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    evening_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    delivery_in_app: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    delivery_telegram: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
