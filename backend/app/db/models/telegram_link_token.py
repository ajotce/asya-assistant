from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.common import IdMixin, TimestampMixin


class TelegramLinkToken(Base, IdMixin, TimestampMixin):
    __tablename__ = "telegram_link_tokens"
    __table_args__ = (
        UniqueConstraint("token_hash", name="uq_telegram_link_tokens_hash"),
        Index("ix_telegram_link_tokens_user_expires", "user_id", "expires_at"),
    )

    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    consumed_by_telegram_user_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
