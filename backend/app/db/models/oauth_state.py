from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Enum as SAEnum, ForeignKey, Index, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.common import IdMixin, IntegrationProvider, TimestampMixin


class OAuthState(Base, IdMixin, TimestampMixin):
    __tablename__ = "oauth_states"
    __table_args__ = (
        UniqueConstraint("state_token", name="uq_oauth_states_state_token"),
        Index("ix_oauth_states_user_provider", "user_id", "provider"),
        Index("ix_oauth_states_expires_at", "expires_at"),
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
    state_token: Mapped[str] = mapped_column(String(255), nullable=False)
    code_verifier: Mapped[str] = mapped_column(String(255), nullable=False)
    redirect_uri: Mapped[str] = mapped_column(String(1000), nullable=False)
    scopes: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    expires_at: Mapped[datetime] = mapped_column(nullable=False)
    used_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    safe_error_metadata: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
