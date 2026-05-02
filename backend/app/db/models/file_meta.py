from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.common import IdMixin


class FileMeta(Base, IdMixin):
    __tablename__ = "file_meta"

    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chat_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("chats.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    content_type: Mapped[str] = mapped_column(String(255), nullable=False)
    size: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    extracted_text_status: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    extracted_text_meta: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
