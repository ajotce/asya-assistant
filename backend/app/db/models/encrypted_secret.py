from __future__ import annotations

from sqlalchemy import ForeignKey, LargeBinary, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.common import IdMixin, TimestampMixin


class EncryptedSecret(Base, IdMixin, TimestampMixin):
    __tablename__ = "encrypted_secrets"
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_encrypted_secret_user_name"),)

    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    secret_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    encrypted_value: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
