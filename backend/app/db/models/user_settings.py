from __future__ import annotations

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.common import TimestampMixin


class UserSettings(Base, TimestampMixin):
    __tablename__ = "user_settings"

    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    assistant_name: Mapped[str] = mapped_column(String(120), nullable=False)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    selected_model: Mapped[str] = mapped_column(String(200), nullable=False)
