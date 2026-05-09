from __future__ import annotations

from sqlalchemy import Enum as SAEnum, ForeignKey, Index, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.common import BriefingKind, IdMixin, TimestampMixin


class Briefing(Base, IdMixin, TimestampMixin):
    __tablename__ = "briefings"
    __table_args__ = (
        Index("ix_briefings_user_kind_created", "user_id", "kind", "created_at"),
    )

    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    kind: Mapped[BriefingKind] = mapped_column(
        SAEnum(BriefingKind, name="briefing_kind", native_enum=False),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    delivered_via: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
