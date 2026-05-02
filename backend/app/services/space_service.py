from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from app.db.models.common import ActivityEntityType, ActivityEventType, UserRole
from app.db.models.space import Space
from app.db.models.space_memory_settings import SpaceMemorySettings
from app.db.models.user import User
from app.repositories.activity_log_repository import ActivityLogRepository
from app.repositories.space_repository import SpaceRepository


class SpaceNotFoundError(ValueError):
    pass


class SpaceValidationError(ValueError):
    pass


class ProtectedSpaceError(ValueError):
    pass


class SpaceService:
    DEFAULT_SPACE_NAME = "Default"
    ADMIN_SPACE_NAME = "Asya-dev"

    def __init__(self, session: Session, repository: Optional[SpaceRepository] = None) -> None:
        self._session = session
        self._spaces = repository or SpaceRepository(session)
        self._activity = ActivityLogRepository(session)

    def ensure_default_spaces(self, user: User) -> tuple[Space, Optional[Space]]:
        default_space = self._spaces.get_default_for_user(user.id)
        if default_space is None:
            default_space = self._spaces.create(
                user_id=user.id,
                name=self.DEFAULT_SPACE_NAME,
                is_default=True,
                is_archived=False,
                is_admin_only=False,
            )
        self._ensure_settings(default_space, user.id)

        admin_space: Optional[Space] = None
        if user.role == UserRole.ADMIN:
            admin_space = self._spaces.get_admin_dev_for_user(user.id)
            if admin_space is None:
                admin_space = self._spaces.create(
                    user_id=user.id,
                    name=self.ADMIN_SPACE_NAME,
                    is_default=False,
                    is_archived=False,
                    is_admin_only=True,
                )
            self._ensure_settings(admin_space, user.id)

        self._session.flush()
        return default_space, admin_space

    def list_spaces(self, user: User) -> list[Space]:
        self.ensure_default_spaces(user)
        spaces = self._spaces.list_for_user(user.id)
        if user.role != UserRole.ADMIN:
            spaces = [item for item in spaces if not item.is_admin_only]
        return spaces

    def get_space_for_user(self, *, user: User, space_id: str) -> Space:
        space = self._spaces.get_for_user(space_id, user.id)
        if space is None or space.is_archived:
            raise SpaceNotFoundError("Пространство не найдено.")
        if space.is_admin_only and user.role != UserRole.ADMIN:
            raise SpaceNotFoundError("Пространство не найдено.")
        return space

    def create_space(self, *, user: User, name: str) -> Space:
        normalized = self._normalize_name(name)
        if normalized.lower() == self.ADMIN_SPACE_NAME.lower() and user.role != UserRole.ADMIN:
            raise SpaceValidationError("Нельзя создать служебное пространство.")
        existing = self._spaces.get_by_name_for_user(user_id=user.id, name=normalized)
        if existing is not None and not existing.is_archived:
            raise SpaceValidationError("Пространство с таким именем уже существует.")

        space = self._spaces.create(
            user_id=user.id,
            name=normalized,
            is_default=False,
            is_archived=False,
            is_admin_only=(normalized == self.ADMIN_SPACE_NAME),
        )
        self._ensure_settings(space, user.id)
        self._activity.create(
            user_id=user.id,
            space_id=space.id,
            event_type=ActivityEventType.SPACE_CREATED,
            entity_type=ActivityEntityType.SPACE,
            entity_id=space.id,
            summary=f"Создано пространство: {space.name}",
            meta={"is_admin_only": bool(space.is_admin_only)},
        )
        self._session.commit()
        self._session.refresh(space)
        return space

    def rename_space(self, *, user: User, space_id: str, name: str) -> Space:
        space = self.get_space_for_user(user=user, space_id=space_id)
        if space.is_admin_only:
            raise ProtectedSpaceError("Служебное пространство нельзя переименовать.")

        normalized = self._normalize_name(name)
        existing = self._spaces.get_by_name_for_user(user_id=user.id, name=normalized)
        if existing is not None and existing.id != space.id and not existing.is_archived:
            raise SpaceValidationError("Пространство с таким именем уже существует.")

        space.name = normalized
        self._spaces.save(space)
        self._activity.create(
            user_id=user.id,
            space_id=space.id,
            event_type=ActivityEventType.SPACE_UPDATED,
            entity_type=ActivityEntityType.SPACE,
            entity_id=space.id,
            summary=f"Переименовано пространство: {space.name}",
        )
        self._session.commit()
        self._session.refresh(space)
        return space

    def archive_space(self, *, user: User, space_id: str) -> Space:
        space = self.get_space_for_user(user=user, space_id=space_id)
        if space.is_default:
            raise ProtectedSpaceError("Нельзя архивировать пространство по умолчанию.")
        if space.is_admin_only:
            raise ProtectedSpaceError("Служебное пространство нельзя архивировать обычной операцией.")

        space.is_archived = True
        self._spaces.save(space)
        self._activity.create(
            user_id=user.id,
            space_id=space.id,
            event_type=ActivityEventType.SPACE_ARCHIVED,
            entity_type=ActivityEntityType.SPACE,
            entity_id=space.id,
            summary=f"Архивировано пространство: {space.name}",
        )
        self._session.commit()
        self._session.refresh(space)
        return space

    def get_space_settings(self, *, user: User, space_id: str) -> SpaceMemorySettings:
        space = self.get_space_for_user(user=user, space_id=space_id)
        settings = self._ensure_settings(space, user.id)
        self._session.flush()
        return settings

    def update_space_settings(
        self,
        *,
        user: User,
        space_id: str,
        memory_read_enabled: bool,
        memory_write_enabled: bool,
        behavior_rules_enabled: bool,
        personality_overlay_enabled: bool,
    ) -> SpaceMemorySettings:
        space = self.get_space_for_user(user=user, space_id=space_id)
        settings = self._ensure_settings(space, user.id)
        settings.memory_read_enabled = memory_read_enabled
        settings.memory_write_enabled = memory_write_enabled
        settings.behavior_rules_enabled = behavior_rules_enabled
        settings.personality_overlay_enabled = personality_overlay_enabled
        self._session.add(settings)
        self._activity.create(
            user_id=user.id,
            space_id=space.id,
            event_type=ActivityEventType.SPACE_UPDATED,
            entity_type=ActivityEntityType.SPACE_SETTINGS,
            entity_id=space.id,
            summary=f"Обновлены настройки пространства: {space.name}",
            meta={
                "memory_read_enabled": memory_read_enabled,
                "memory_write_enabled": memory_write_enabled,
                "behavior_rules_enabled": behavior_rules_enabled,
                "personality_overlay_enabled": personality_overlay_enabled,
            },
        )
        self._session.commit()
        self._session.refresh(settings)
        return settings

    def get_default_space(self, user: User) -> Space:
        default_space, _ = self.ensure_default_spaces(user)
        return default_space

    def _ensure_settings(self, space: Space, user_id: str) -> SpaceMemorySettings:
        settings = self._session.get(SpaceMemorySettings, space.id)
        if settings is None:
            settings = SpaceMemorySettings(
                space_id=space.id,
                user_id=user_id,
                memory_read_enabled=True,
                memory_write_enabled=True,
                behavior_rules_enabled=True,
                personality_overlay_enabled=True,
            )
            self._session.add(settings)
            self._session.flush()
        return settings

    @staticmethod
    def _normalize_name(name: str) -> str:
        normalized = name.strip()
        if not normalized:
            raise SpaceValidationError("Название пространства не должно быть пустым.")
        return normalized
