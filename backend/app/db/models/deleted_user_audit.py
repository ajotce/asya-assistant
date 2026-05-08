from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.common import IdMixin


class DeletedUserAudit(Base, IdMixin):
    __tablename__ = "deleted_user_audits"
    __table_args__ = (Index("ix_deleted_user_audits_user_deleted", "user_id", "deleted_at"),)

    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    deleted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    had_export: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
