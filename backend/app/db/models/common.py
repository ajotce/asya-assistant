from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import uuid4

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column


def uuid_str() -> str:
    return str(uuid4())


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class IdMixin:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)


class UserRole(str, Enum):
    USER = "user"
    ADMIN = "admin"


class UserStatus(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"
    DISABLED = "disabled"


class ChatKind(str, Enum):
    REGULAR = "regular"
    BASE = "base"
    PRIVATE_ENCRYPTED = "private_encrypted"


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


class AccessRequestStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


class MemoryStatus(str, Enum):
    CONFIRMED = "confirmed"
    INFERRED = "inferred"
    NEEDS_REVIEW = "needs_review"
    OUTDATED = "outdated"
    FORBIDDEN = "forbidden"
    DELETED = "deleted"


class RuleScope(str, Enum):
    GLOBAL = "global"
    USER = "user"
    SPACE = "space"


class RuleStrictness(str, Enum):
    SOFT = "soft"
    NORMAL = "normal"
    HARD = "hard"


class RuleStatus(str, Enum):
    ACTIVE = "active"
    DISABLED = "disabled"
    ARCHIVED = "archived"


class RuleSource(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class PersonalityScope(str, Enum):
    BASE = "base"
    SPACE_OVERLAY = "space_overlay"


class MemoryChangeKind(str, Enum):
    CREATE = "create"
    UPDATE = "update"
    STATUS = "status"
    DELETE = "delete"
    ROLLBACK = "rollback"


class ActivityEventType(str, Enum):
    SPACE_CREATED = "space_created"
    SPACE_UPDATED = "space_updated"
    SPACE_ARCHIVED = "space_archived"
    MEMORY_FACT_CREATED = "memory_fact_created"
    MEMORY_EPISODE_CREATED = "memory_episode_created"
    MEMORY_STATUS_CHANGED = "memory_status_changed"
    RULE_APPLIED = "rule_applied"
    PERSONALITY_APPLIED = "personality_applied"
    MEMORY_USED_IN_RESPONSE = "memory_used_in_response"
    MEMORY_SNAPSHOT_CREATED = "memory_snapshot_created"
    MEMORY_ROLLBACK = "memory_rollback"
    NOTIFICATION_SENT = "notification_sent"
    DIARY_ENTRY_PROCESSED = "diary_entry_processed"
    OBSERVATION_CREATED = "observation_created"
    OBSERVATION_UPDATED = "observation_updated"
    NOTIFICATION_CENTER = "notification_center"


class ActivityEntityType(str, Enum):
    SPACE = "space"
    SPACE_SETTINGS = "space_settings"
    USER_PROFILE_FACT = "user_profile_fact"
    MEMORY_EPISODE = "memory_episode"
    MEMORY_CHUNK = "memory_chunk"
    BEHAVIOR_RULE = "behavior_rule"
    PERSONALITY_PROFILE = "personality_profile"
    MEMORY_CHANGE = "memory_change"
    MEMORY_SNAPSHOT = "memory_snapshot"
    NOTIFICATION = "notification"


class VoiceProvider(str, Enum):
    MOCK = "mock"
    YANDEX_SPEECHKIT = "yandex_speechkit"
    GIGACHAT = "gigachat"


class VoiceGender(str, Enum):
    FEMALE = "female"
    MALE = "male"
    NEUTRAL = "neutral"
    DIARY_ENTRY = "diary_entry"
    OBSERVATION = "observation"


class IntegrationProvider(str, Enum):
    LINEAR = "linear"
    GOOGLE_CALENDAR = "google_calendar"
    TODOIST = "todoist"
    GMAIL = "gmail"
    GOOGLE_DRIVE = "google_drive"
    TELEGRAM = "telegram"


class IntegrationConnectionStatus(str, Enum):
    NOT_CONNECTED = "not_connected"
    CONNECTED = "connected"
    EXPIRED = "expired"
    REVOKED = "revoked"
    ERROR = "error"


class ObservationStatus(str, Enum):
    NEW = "new"
    SEEN = "seen"
    DISMISSED = "dismissed"
    ACTIONED = "actioned"


class ObservationSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
