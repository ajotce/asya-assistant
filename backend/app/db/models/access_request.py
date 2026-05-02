from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.common import AccessRequestStatus, IdMixin, TimestampMixin


class AccessRequest(Base, IdMixin, TimestampMixin):
    __tablename__ = "access_requests"

    email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    reason: Mapped[str] = mapped_column(String(1000), nullable=False)
    status: Mapped[AccessRequestStatus] = mapped_column(
        SAEnum(AccessRequestStatus, name="access_request_status", native_enum=False),
        nullable=False,
        default=AccessRequestStatus.PENDING,
        index=True,
    )
    token_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, unique=True)
    approved_by: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
