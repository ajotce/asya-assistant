from __future__ import annotations

from typing import Optional

from sqlalchemy import Enum as SAEnum, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.common import IdMixin, RuleScope, RuleSource, RuleStatus, RuleStrictness, TimestampMixin


class BehaviorRule(Base, IdMixin, TimestampMixin):
    __tablename__ = "behavior_rules"
    __table_args__ = (
        Index("ix_behavior_rules_user_scope", "user_id", "scope"),
        Index("ix_behavior_rules_user_space", "user_id", "space_id"),
        Index("ix_behavior_rules_user_status", "user_id", "status"),
    )

    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    space_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("spaces.id", ondelete="SET NULL"), nullable=True)
    scope: Mapped[RuleScope] = mapped_column(
        SAEnum(RuleScope, name="rule_scope", native_enum=False),
        nullable=False,
        default=RuleScope.USER,
    )
    strictness: Mapped[RuleStrictness] = mapped_column(
        SAEnum(RuleStrictness, name="rule_strictness", native_enum=False),
        nullable=False,
        default=RuleStrictness.NORMAL,
    )
    status: Mapped[RuleStatus] = mapped_column(
        SAEnum(RuleStatus, name="rule_status", native_enum=False),
        nullable=False,
        default=RuleStatus.ACTIVE,
    )
    source: Mapped[RuleSource] = mapped_column(
        SAEnum(RuleSource, name="rule_source", native_enum=False),
        nullable=False,
        default=RuleSource.USER,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    instruction: Mapped[str] = mapped_column(Text, nullable=False)
