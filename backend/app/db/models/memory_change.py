from __future__ import annotations

from typing import Optional

from sqlalchemy import Enum as SAEnum, ForeignKey, Index, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.common import IdMixin, MemoryChangeKind, TimestampMixin


class MemoryChange(Base, IdMixin, TimestampMixin):
    __tablename__ = "memory_changes"
    __table_args__ = (Index("ix_memory_changes_user_space", "user_id", "space_id"),)

    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    space_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("spaces.id", ondelete="SET NULL"), nullable=True)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    change_kind: Mapped[MemoryChangeKind] = mapped_column(
        SAEnum(MemoryChangeKind, name="memory_change_kind", native_enum=False),
        nullable=False,
    )
    old_value: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    new_value: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
