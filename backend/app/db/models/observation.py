from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Index, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.common import IdMixin, ObservationSeverity, ObservationStatus, TimestampMixin


class Observation(Base, IdMixin, TimestampMixin):
    __tablename__ = "observations"
    __table_args__ = (
        Index("ix_observations_user_status", "user_id", "status"),
        Index("ix_observations_user_detector", "user_id", "detector"),
        Index("ix_observations_user_dedup", "user_id", "dedup_key"),
    )

    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    rule_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("observation_rules.id", ondelete="SET NULL"),
        nullable=True,
    )
    detector: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    details: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[ObservationSeverity] = mapped_column(
        SAEnum(ObservationSeverity, name="observation_severity", native_enum=False),
        nullable=False,
        default=ObservationSeverity.INFO,
    )
    status: Mapped[ObservationStatus] = mapped_column(
        SAEnum(ObservationStatus, name="observation_status", native_enum=False),
        nullable=False,
        default=ObservationStatus.NEW,
    )
    context_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    dedup_key: Mapped[str] = mapped_column(String(255), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    postponed_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
