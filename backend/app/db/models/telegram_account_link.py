from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.common import IdMixin, TimestampMixin


class TelegramAccountLink(Base, IdMixin, TimestampMixin):
    __tablename__ = "telegram_account_links"
    __table_args__ = (
        UniqueConstraint("telegram_user_id", name="uq_telegram_account_links_tg_user"),
        Index("ix_telegram_account_links_user_active", "user_id", "is_active"),
    )

    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    telegram_user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    telegram_chat_id: Mapped[str] = mapped_column(String(64), nullable=False)
    telegram_username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    linked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    unlinked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)
