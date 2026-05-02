from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Enum as SAEnum, ForeignKey, Index, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.common import IdMixin, IntegrationConnectionStatus, IntegrationProvider, TimestampMixin


class IntegrationConnection(Base, IdMixin, TimestampMixin):
    __tablename__ = "integration_connections"
    __table_args__ = (
        UniqueConstraint("user_id", "provider", name="uq_integration_connections_user_provider"),
        Index("ix_integration_connections_user_status", "user_id", "status"),
    )

    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider: Mapped[IntegrationProvider] = mapped_column(
        SAEnum(IntegrationProvider, name="integration_provider", native_enum=False),
        nullable=False,
    )
    status: Mapped[IntegrationConnectionStatus] = mapped_column(
        SAEnum(IntegrationConnectionStatus, name="integration_connection_status", native_enum=False),
        nullable=False,
        default=IntegrationConnectionStatus.NOT_CONNECTED,
    )
    scopes: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    connected_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    last_refresh_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    last_sync_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    safe_error_metadata: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
