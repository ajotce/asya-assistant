from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.common import IdMixin, TimestampMixin


class Briefing(Base, IdMixin, TimestampMixin):
    __tablename__ = "briefings"

    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    delivered_in_app: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    delivered_telegram: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    source_meta: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
