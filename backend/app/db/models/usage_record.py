from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.common import IdMixin


class UsageRecord(Base, IdMixin):
    __tablename__ = "usage_records"

    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chat_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("chats.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    kind: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    model: Mapped[str] = mapped_column(String(255), nullable=False)
    prompt_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
