from __future__ import annotations

from typing import Optional

from sqlalchemy import ForeignKey, Index, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.common import IdMixin, TimestampMixin


class DocumentTemplate(Base, IdMixin, TimestampMixin):
    __tablename__ = "document_templates"
    __table_args__ = (
        Index("ix_document_templates_user_created", "user_id", "created_at"),
    )

    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(2000), nullable=True)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    file_id: Mapped[str] = mapped_column(String(512), nullable=False)
    fields: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    output_settings: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
