from __future__ import annotations

from sqlalchemy import ForeignKey, Index, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.common import IdMixin, TimestampMixin


class ObservedEntityStateChange(Base, IdMixin, TimestampMixin):
    __tablename__ = "observed_entity_state_changes"
    __table_args__ = (
        Index("ix_observed_entity_state_changes_user_created", "user_id", "created_at"),
        Index("ix_observed_entity_state_changes_snapshot", "snapshot_id"),
    )

    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    snapshot_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("observed_entity_snapshots.id", ondelete="CASCADE"),
        nullable=False,
    )
    previous_snapshot_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("observed_entity_snapshots.id", ondelete="SET NULL"),
        nullable=True,
    )
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_ref: Mapped[str] = mapped_column(String(255), nullable=False)
    change_kind: Mapped[str] = mapped_column(String(64), nullable=False)
    changed_fields: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    old_state: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    new_state: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
