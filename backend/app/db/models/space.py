from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.common import IdMixin, TimestampMixin


class Space(Base, IdMixin, TimestampMixin):
    __tablename__ = "spaces"
    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_spaces_user_name"),
        Index("ix_spaces_user_archived", "user_id", "is_archived"),
    )

    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_admin_only: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
