from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.common import IdMixin, TimestampMixin, UserExportStatus


class UserExport(Base, IdMixin, TimestampMixin):
    __tablename__ = "user_exports"
    __table_args__ = (
        Index("ix_user_exports_user_status", "user_id", "status"),
    )

    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[UserExportStatus] = mapped_column(
        SAEnum(UserExportStatus, name="user_export_status", native_enum=False),
        nullable=False,
        default=UserExportStatus.PENDING,
    )
    file_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    download_token: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
