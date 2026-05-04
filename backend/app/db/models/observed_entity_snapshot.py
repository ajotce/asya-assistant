from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.common import IdMixin, TimestampMixin


class ObservedEntitySnapshot(Base, IdMixin, TimestampMixin):
    __tablename__ = "observed_entity_snapshots"
    __table_args__ = (
        Index("ix_observed_entity_snapshots_user_observed_at", "user_id", "observed_at"),
        Index(
            "ix_observed_entity_snapshots_lookup",
            "user_id",
            "provider",
            "entity_type",
            "entity_ref",
            "observed_at",
        ),
        UniqueConstraint(
            "user_id",
            "provider",
            "entity_type",
            "entity_ref",
            "digest",
            name="uq_observed_entity_snapshots_dedup",
        ),
    )

    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_ref: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_state: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    digest: Mapped[str] = mapped_column(String(64), nullable=False)
