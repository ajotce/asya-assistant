from __future__ import annotations

from sqlalchemy import Enum as SAEnum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.common import TimestampMixin, VoiceGender, VoiceProvider


class UserVoiceSettings(Base, TimestampMixin):
    __tablename__ = "user_voice_settings"

    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    assistant_name: Mapped[str] = mapped_column(String(120), nullable=False)
    voice_gender: Mapped[VoiceGender] = mapped_column(
        SAEnum(VoiceGender, name="voice_gender", native_enum=False),
        nullable=False,
        default=VoiceGender.FEMALE,
    )
    stt_provider: Mapped[VoiceProvider] = mapped_column(
        SAEnum(VoiceProvider, name="voice_provider_stt", native_enum=False),
        nullable=False,
        default=VoiceProvider.MOCK,
    )
    tts_provider: Mapped[VoiceProvider] = mapped_column(
        SAEnum(VoiceProvider, name="voice_provider_tts", native_enum=False),
        nullable=False,
        default=VoiceProvider.MOCK,
    )
    tts_enabled: Mapped[bool] = mapped_column(nullable=False, default=False)
