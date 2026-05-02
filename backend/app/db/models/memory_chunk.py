from __future__ import annotations

from typing import Optional

from sqlalchemy import Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.common import IdMixin, TimestampMixin


class MemoryChunk(Base, IdMixin, TimestampMixin):
    __tablename__ = "memory_chunks"
    __table_args__ = (
        Index("ix_memory_chunks_user_space", "user_id", "space_id"),
        Index("ix_memory_chunks_episode_position", "memory_episode_id", "chunk_index"),
    )

    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    memory_episode_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("memory_episodes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    space_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("spaces.id", ondelete="SET NULL"), nullable=True)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding_model: Mapped[str] = mapped_column(String(255), nullable=False)
    embedding: Mapped[str] = mapped_column(Text, nullable=False)
    relevance_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
