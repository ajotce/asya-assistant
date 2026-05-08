from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.common import IdMixin


class DeletedUserAudit(Base, IdMixin):
    __tablename__ = "deleted_user_audit"

    deleted_user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    deleted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    initiated_by_user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    export_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
