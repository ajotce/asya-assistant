from __future__ import annotations

from typing import Optional

from sqlalchemy import Boolean, Enum as SAEnum, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.common import IdMixin, PersonalityScope, TimestampMixin


class AssistantPersonalityProfile(Base, IdMixin, TimestampMixin):
    __tablename__ = "assistant_personality_profiles"
    __table_args__ = (
        UniqueConstraint("user_id", "scope", "space_id", name="uq_personality_user_scope_space"),
        Index("ix_personality_profiles_user_scope", "user_id", "scope"),
    )

    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    space_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("spaces.id", ondelete="SET NULL"), nullable=True)
    scope: Mapped[PersonalityScope] = mapped_column(
        SAEnum(PersonalityScope, name="personality_scope", native_enum=False),
        nullable=False,
        default=PersonalityScope.BASE,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False, default="Asya")
    tone: Mapped[str] = mapped_column(String(120), nullable=False, default="balanced")
    style_notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    humor_level: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    initiative_level: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    can_gently_disagree: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    address_user_by_name: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
