from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.db.models.assistant_personality_profile import AssistantPersonalityProfile
from app.db.models.common import (
    ActivityEntityType,
    ActivityEventType,
    MemoryChangeKind,
    MemoryStatus,
    PersonalityScope,
    RuleScope,
    RuleSource,
    RuleStatus,
    RuleStrictness,
)
from app.db.models.space_memory_settings import SpaceMemorySettings
from app.db.models.user import User
from app.repositories.activity_log_repository import ActivityLogRepository
from app.repositories.behavior_rule_repository import BehaviorRuleRepository
from app.repositories.memory_change_repository import MemoryChangeRepository
from app.repositories.memory_episode_repository import MemoryEpisodeRepository
from app.repositories.memory_snapshot_repository import MemorySnapshotRepository
from app.repositories.personality_profile_repository import PersonalityProfileRepository
from app.repositories.user_profile_fact_repository import UserProfileFactRepository
from app.repositories.user_repository import UserRepository
from app.services.space_service import SpaceNotFoundError, SpaceService


class MemoryNotFoundError(ValueError):
    pass


class MemoryValidationError(ValueError):
    pass


@dataclass
class FactCreatePayload:
    key: str
    value: str
    status: MemoryStatus
    source: str
    space_id: str | None


@dataclass
class RuleCreatePayload:
    title: str
    instruction: str
    scope: RuleScope
    strictness: RuleStrictness
    source: RuleSource
    status: RuleStatus
    space_id: str | None


class MemoryService:
    AUTO_SNAPSHOT_CHANGE_THRESHOLD = 25

    def __init__(self, session: Session) -> None:
        self._session = session
        self._facts = UserProfileFactRepository(session)
        self._rules = BehaviorRuleRepository(session)
        self._episodes = MemoryEpisodeRepository(session)
        self._changes = MemoryChangeRepository(session)
        self._activity = ActivityLogRepository(session)
        self._snapshots = MemorySnapshotRepository(session)
        self._personality = PersonalityProfileRepository(session)
        self._spaces = SpaceService(session)
        self._users = UserRepository(session)

    def list_facts(self, *, user: User, active_only: bool = True):
        items = self._facts.list_for_user(user.id, include_deleted=not active_only)
        if active_only:
            items = [x for x in items if x.status not in {MemoryStatus.FORBIDDEN, MemoryStatus.DELETED}]
        return items

    def create_fact(self, *, user: User, payload: FactCreatePayload):
        self._validate_fact_status(payload.status)
        self._ensure_space_allowed(user, payload.space_id)
        item = self._facts.create(
            user_id=user.id,
            key=payload.key.strip(),
            value=payload.value.strip(),
            status=payload.status,
            source=payload.source.strip() or "user",
            space_id=payload.space_id,
        )
        self._record_change_and_activity(
            user_id=user.id,
            space_id=item.space_id,
            entity_type="user_profile_fact",
            entity_id=item.id,
            change_kind=MemoryChangeKind.CREATE,
            old_value=None,
            new_value=self._fact_snapshot(item),
            event_type=ActivityEventType.MEMORY_FACT_CREATED,
            activity_entity=ActivityEntityType.USER_PROFILE_FACT,
            summary=f"Создан факт памяти: {item.key}",
        )
        self._session.commit()
        self._session.refresh(item)
        return item

    def update_fact(self, *, user: User, fact_id: str, key: str, value: str, source: str | None):
        item = self._get_fact_for_user(user.id, fact_id)
        before = self._fact_snapshot(item)
        item.key = key.strip() or item.key
        item.value = value.strip() or item.value
        if source is not None and source.strip():
            item.source = source.strip()
        self._facts.save(item)
        self._record_change_and_activity(
            user_id=user.id,
            space_id=item.space_id,
            entity_type="user_profile_fact",
            entity_id=item.id,
            change_kind=MemoryChangeKind.UPDATE,
            old_value=before,
            new_value=self._fact_snapshot(item),
            event_type=ActivityEventType.MEMORY_STATUS_CHANGED,
            activity_entity=ActivityEntityType.USER_PROFILE_FACT,
            summary=f"Обновлен факт памяти: {item.key}",
        )
        self._session.commit()
        self._session.refresh(item)
        return item

    def set_fact_status(self, *, user: User, fact_id: str, status: MemoryStatus):
        self._validate_fact_status(status)
        item = self._get_fact_for_user(user.id, fact_id)
        before = self._fact_snapshot(item)
        item.status = status
        self._facts.save(item)
        self._record_change_and_activity(
            user_id=user.id,
            space_id=item.space_id,
            entity_type="user_profile_fact",
            entity_id=item.id,
            change_kind=MemoryChangeKind.STATUS,
            old_value=before,
            new_value=self._fact_snapshot(item),
            event_type=ActivityEventType.MEMORY_STATUS_CHANGED,
            activity_entity=ActivityEntityType.USER_PROFILE_FACT,
            summary=f"Изменен статус факта памяти: {item.key} -> {item.status.value}",
        )
        self._session.commit()
        self._session.refresh(item)
        return item

    def forbid_fact(self, *, user: User, fact_id: str):
        return self.set_fact_status(user=user, fact_id=fact_id, status=MemoryStatus.FORBIDDEN)

    def list_rules(self, *, user: User, active_only: bool = False):
        return self._rules.list_for_user(user.id, active_only=active_only)

    def create_rule(self, *, user: User, payload: RuleCreatePayload):
        self._ensure_scope_space(user, payload.scope, payload.space_id)
        item = self._rules.create(
            user_id=user.id,
            space_id=payload.space_id,
            scope=payload.scope,
            strictness=payload.strictness,
            status=payload.status,
            source=payload.source,
            title=payload.title.strip(),
            instruction=payload.instruction.strip(),
        )
        self._record_change_and_activity(
            user_id=user.id,
            space_id=item.space_id,
            entity_type="behavior_rule",
            entity_id=item.id,
            change_kind=MemoryChangeKind.CREATE,
            old_value=None,
            new_value=self._rule_snapshot(item),
            event_type=ActivityEventType.RULE_APPLIED,
            activity_entity=ActivityEntityType.BEHAVIOR_RULE,
            summary=f"Создано правило: {item.title}",
        )
        self._session.commit()
        self._session.refresh(item)
        return item

    def update_rule(
        self,
        *,
        user: User,
        rule_id: str,
        title: str,
        instruction: str,
        scope: RuleScope,
        strictness: RuleStrictness,
        source: RuleSource,
        status: RuleStatus,
        space_id: str | None,
    ):
        self._ensure_scope_space(user, scope, space_id)
        item = self._get_rule_for_user(user.id, rule_id)
        before = self._rule_snapshot(item)
        item.title = title.strip() or item.title
        item.instruction = instruction.strip() or item.instruction
        item.scope = scope
        item.strictness = strictness
        item.source = source
        item.status = status
        item.space_id = space_id
        self._rules.save(item)
        self._record_change_and_activity(
            user_id=user.id,
            space_id=item.space_id,
            entity_type="behavior_rule",
            entity_id=item.id,
            change_kind=MemoryChangeKind.UPDATE,
            old_value=before,
            new_value=self._rule_snapshot(item),
            event_type=ActivityEventType.RULE_APPLIED,
            activity_entity=ActivityEntityType.BEHAVIOR_RULE,
            summary=f"Обновлено правило: {item.title}",
        )
        self._session.commit()
        self._session.refresh(item)
        return item

    def disable_rule(self, *, user: User, rule_id: str):
        item = self._get_rule_for_user(user.id, rule_id)
        before = self._rule_snapshot(item)
        item.status = RuleStatus.DISABLED
        self._rules.save(item)
        self._record_change_and_activity(
            user_id=user.id,
            space_id=item.space_id,
            entity_type="behavior_rule",
            entity_id=item.id,
            change_kind=MemoryChangeKind.STATUS,
            old_value=before,
            new_value=self._rule_snapshot(item),
            event_type=ActivityEventType.RULE_APPLIED,
            activity_entity=ActivityEntityType.BEHAVIOR_RULE,
            summary=f"Отключено правило: {item.title}",
        )
        self._session.commit()
        self._session.refresh(item)
        return item

    def list_episodes(self, *, user: User, active_only: bool = True):
        return self._episodes.list_for_user(user.id, active_only=active_only)

    def create_episode(
        self,
        *,
        user: User,
        chat_id: str,
        summary: str,
        status: MemoryStatus,
        source: str,
        space_id: str | None,
    ):
        self._validate_fact_status(status)
        self._ensure_space_allowed(user, space_id)
        item = self._episodes.create(
            user_id=user.id,
            chat_id=chat_id,
            summary=summary.strip(),
            status=status,
            source=source.strip() or "assistant",
            space_id=space_id,
        )
        self._record_change_and_activity(
            user_id=user.id,
            space_id=item.space_id,
            entity_type="memory_episode",
            entity_id=item.id,
            change_kind=MemoryChangeKind.CREATE,
            old_value=None,
            new_value={
                "id": item.id,
                "chat_id": item.chat_id,
                "summary": item.summary,
                "status": item.status.value,
                "source": item.source,
                "space_id": item.space_id,
            },
            event_type=ActivityEventType.MEMORY_EPISODE_CREATED,
            activity_entity=ActivityEntityType.MEMORY_EPISODE,
            summary="Создан эпизод памяти",
        )
        self._session.commit()
        self._session.refresh(item)
        return item

    def list_changes(self, *, user: User):
        return self._changes.list_for_user(user.id)

    def get_or_create_personality(self, *, user: User) -> AssistantPersonalityProfile:
        item = self._personality.get_base_for_user(user.id)
        if item is None:
            item = AssistantPersonalityProfile(
                user_id=user.id,
                scope=PersonalityScope.BASE,
                space_id=None,
                name="Asya",
                tone="balanced",
                style_notes="",
                humor_level=1,
                initiative_level=1,
                can_gently_disagree=True,
                address_user_by_name=True,
                is_active=True,
            )
            self._personality.save(item)
            self._record_change_and_activity(
                user_id=user.id,
                space_id=None,
                entity_type="personality_profile",
                entity_id=item.id,
                change_kind=MemoryChangeKind.CREATE,
                old_value=None,
                new_value=self._personality_snapshot(item),
                event_type=ActivityEventType.PERSONALITY_APPLIED,
                activity_entity=ActivityEntityType.PERSONALITY_PROFILE,
                summary="Создан базовый профиль личности",
            )
            self._session.commit()
            self._session.refresh(item)
        return item

    def update_personality(
        self,
        *,
        user: User,
        name: str,
        tone: str,
        style_notes: str,
        humor_level: int,
        initiative_level: int,
        can_gently_disagree: bool,
        address_user_by_name: bool,
        is_active: bool,
    ):
        self._validate_personality_levels(humor_level=humor_level, initiative_level=initiative_level)
        item = self.get_or_create_personality(user=user)
        before = self._personality_snapshot(item)
        item.name = name.strip() or item.name
        item.tone = tone.strip() or item.tone
        item.style_notes = style_notes
        item.humor_level = humor_level
        item.initiative_level = initiative_level
        item.can_gently_disagree = can_gently_disagree
        item.address_user_by_name = address_user_by_name
        item.is_active = is_active
        self._personality.save(item)
        self._record_change_and_activity(
            user_id=user.id,
            space_id=None,
            entity_type="personality_profile",
            entity_id=item.id,
            change_kind=MemoryChangeKind.UPDATE,
            old_value=before,
            new_value=self._personality_snapshot(item),
            event_type=ActivityEventType.PERSONALITY_APPLIED,
            activity_entity=ActivityEntityType.PERSONALITY_PROFILE,
            summary="Обновлен профиль личности",
        )
        self._session.commit()
        self._session.refresh(item)
        return item

    def get_or_create_personality_overlay(self, *, user: User, space_id: str) -> AssistantPersonalityProfile:
        self._ensure_space_allowed(user, space_id)
        item = self._personality.get_space_overlay_any_for_user(user_id=user.id, space_id=space_id)
        if item is None:
            item = AssistantPersonalityProfile(
                user_id=user.id,
                scope=PersonalityScope.SPACE_OVERLAY,
                space_id=space_id,
                name="Asya",
                tone="balanced",
                style_notes="",
                humor_level=1,
                initiative_level=1,
                can_gently_disagree=True,
                address_user_by_name=True,
                is_active=True,
            )
            self._personality.save(item)
            self._record_change_and_activity(
                user_id=user.id,
                space_id=space_id,
                entity_type="personality_profile",
                entity_id=item.id,
                change_kind=MemoryChangeKind.CREATE,
                old_value=None,
                new_value=self._personality_snapshot(item),
                event_type=ActivityEventType.PERSONALITY_APPLIED,
                activity_entity=ActivityEntityType.PERSONALITY_PROFILE,
                summary="Создан personality overlay пространства",
            )
            self._session.commit()
            self._session.refresh(item)
        return item

    def update_personality_overlay(
        self,
        *,
        user: User,
        space_id: str,
        name: str,
        tone: str,
        style_notes: str,
        humor_level: int,
        initiative_level: int,
        can_gently_disagree: bool,
        address_user_by_name: bool,
        is_active: bool,
    ) -> AssistantPersonalityProfile:
        self._validate_personality_levels(humor_level=humor_level, initiative_level=initiative_level)
        item = self.get_or_create_personality_overlay(user=user, space_id=space_id)
        before = self._personality_snapshot(item)
        item.name = name.strip() or item.name
        item.tone = tone.strip() or item.tone
        item.style_notes = style_notes
        item.humor_level = humor_level
        item.initiative_level = initiative_level
        item.can_gently_disagree = can_gently_disagree
        item.address_user_by_name = address_user_by_name
        item.is_active = is_active
        self._personality.save(item)
        self._record_change_and_activity(
            user_id=user.id,
            space_id=space_id,
            entity_type="personality_profile",
            entity_id=item.id,
            change_kind=MemoryChangeKind.UPDATE,
            old_value=before,
            new_value=self._personality_snapshot(item),
            event_type=ActivityEventType.PERSONALITY_APPLIED,
            activity_entity=ActivityEntityType.PERSONALITY_PROFILE,
            summary="Обновлен personality overlay пространства",
        )
        self._session.commit()
        self._session.refresh(item)
        return item

    def create_snapshot(self, *, user: User, label: str, space_id: str | None):
        self._ensure_space_allowed(user, space_id)
        normalized_label = label.strip()
        if not normalized_label:
            raise MemoryValidationError("Название snapshot не должно быть пустым.")
        payload = self._build_snapshot_payload(user=user, space_id=space_id)
        item = self._snapshots.create(
            user_id=user.id,
            space_id=space_id,
            label=normalized_label,
            payload=payload,
        )
        self._activity.create(
            user_id=user.id,
            space_id=space_id,
            event_type=ActivityEventType.MEMORY_SNAPSHOT_CREATED,
            entity_type=ActivityEntityType.MEMORY_SNAPSHOT,
            entity_id=item.id,
            summary=f"Создан snapshot памяти: {item.label}",
            meta={
                "facts_count": len(payload["facts"]),
                "rules_count": len(payload["rules"]),
                "episodes_count": len(payload["episodes"]),
            },
        )
        self._session.commit()
        self._session.refresh(item)
        return item

    def get_snapshot_for_user(self, *, user: User, snapshot_id: str):
        item = self._snapshots.get_for_user(snapshot_id, user.id)
        if item is None:
            raise MemoryNotFoundError("Snapshot не найден.")
        return item

    def get_snapshot_summary(self, *, user: User, snapshot_id: str) -> dict:
        item = self.get_snapshot_for_user(user=user, snapshot_id=snapshot_id)
        payload = item.payload if isinstance(item.payload, dict) else {}
        facts = payload.get("facts", []) if isinstance(payload.get("facts"), list) else []
        rules = payload.get("rules", []) if isinstance(payload.get("rules"), list) else []
        episodes = payload.get("episodes", []) if isinstance(payload.get("episodes"), list) else []
        personalities = payload.get("personalities", []) if isinstance(payload.get("personalities"), list) else []
        settings = payload.get("space_settings", []) if isinstance(payload.get("space_settings"), list) else []
        return {
            "id": item.id,
            "label": item.label,
            "space_id": item.space_id,
            "created_at": item.created_at.isoformat(),
            "updated_at": item.updated_at.isoformat(),
            "facts_count": len(facts),
            "rules_count": len(rules),
            "episodes_count": len(episodes),
            "personality_profiles_count": len(personalities),
            "space_settings_count": len(settings),
        }

    def rollback_to_snapshot(self, *, user: User, snapshot_id: str):
        snapshot = self.get_snapshot_for_user(user=user, snapshot_id=snapshot_id)
        payload = snapshot.payload if isinstance(snapshot.payload, dict) else {}
        self._apply_facts_rollback(user_id=user.id, facts_payload=payload.get("facts"))
        self._apply_rules_rollback(user_id=user.id, rules_payload=payload.get("rules"))
        self._apply_personalities_rollback(user_id=user.id, profiles_payload=payload.get("personalities"))
        self._apply_space_settings_rollback(user=user, settings_payload=payload.get("space_settings"))
        self._apply_episodes_rollback(user_id=user.id, episodes_payload=payload.get("episodes"))

        self._changes.create(
            user_id=user.id,
            space_id=snapshot.space_id,
            entity_type="memory_snapshot",
            entity_id=snapshot.id,
            change_kind=MemoryChangeKind.ROLLBACK,
            old_value={"snapshot_id": snapshot.id, "label": snapshot.label},
            new_value={"result": "applied"},
        )
        self._activity.create(
            user_id=user.id,
            space_id=snapshot.space_id,
            event_type=ActivityEventType.MEMORY_ROLLBACK,
            entity_type=ActivityEntityType.MEMORY_SNAPSHOT,
            entity_id=snapshot.id,
            summary=f"Выполнен rollback по snapshot: {snapshot.label}",
            meta={"snapshot_id": snapshot.id},
        )
        self._session.commit()
        return snapshot

    def list_snapshots(self, *, user: User, space_id: str | None = None, limit: int = 100):
        if space_id is not None:
            self._ensure_space_allowed(user, space_id)
        return self._snapshots.list_for_user(user.id, space_id=space_id, limit=limit)

    def list_activity(
        self,
        *,
        user: User,
        limit: int = 100,
        event_type: ActivityEventType | None = None,
        entity_type: ActivityEntityType | None = None,
        space_id: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ):
        if space_id is not None:
            self._ensure_space_allowed(user, space_id)
        return self._activity.list_for_user(
            user.id,
            limit=limit,
            event_type=event_type,
            entity_type=entity_type,
            space_id=space_id,
            date_from=date_from,
            date_to=date_to,
        )

    def _get_fact_for_user(self, user_id: str, fact_id: str):
        item = self._facts.get_for_user(fact_id, user_id)
        if item is None:
            raise MemoryNotFoundError("Факт памяти не найден.")
        return item

    def _get_rule_for_user(self, user_id: str, rule_id: str):
        item = self._rules.get_for_user(rule_id, user_id)
        if item is None:
            raise MemoryNotFoundError("Правило не найдено.")
        return item

    def _ensure_scope_space(self, user: User, scope: RuleScope, space_id: str | None) -> None:
        if scope == RuleScope.SPACE and not space_id:
            raise MemoryValidationError("Для scope=space требуется space_id.")
        if scope != RuleScope.SPACE and space_id is not None:
            raise MemoryValidationError("space_id допустим только для scope=space.")
        self._ensure_space_allowed(user, space_id)

    def _ensure_space_allowed(self, user: User, space_id: str | None) -> None:
        if space_id is None:
            return
        try:
            self._spaces.get_space_for_user(user=user, space_id=space_id)
        except SpaceNotFoundError as exc:
            raise MemoryValidationError("Пространство недоступно.") from exc

    @staticmethod
    def _validate_fact_status(status: MemoryStatus) -> None:
        if status not in {
            MemoryStatus.CONFIRMED,
            MemoryStatus.INFERRED,
            MemoryStatus.NEEDS_REVIEW,
            MemoryStatus.OUTDATED,
            MemoryStatus.FORBIDDEN,
            MemoryStatus.DELETED,
        }:
            raise MemoryValidationError("Неподдерживаемый статус памяти.")

    def _record_change_and_activity(
        self,
        *,
        user_id: str,
        space_id: str | None,
        entity_type: str,
        entity_id: str,
        change_kind: MemoryChangeKind,
        old_value: dict | None,
        new_value: dict | None,
        event_type: ActivityEventType,
        activity_entity: ActivityEntityType,
        summary: str,
    ) -> None:
        self._changes.create(
            user_id=user_id,
            space_id=space_id,
            entity_type=entity_type,
            entity_id=entity_id,
            change_kind=change_kind,
            old_value=old_value,
            new_value=new_value,
        )
        self._activity.create(
            user_id=user_id,
            space_id=space_id,
            event_type=event_type,
            entity_type=activity_entity,
            entity_id=entity_id,
            summary=summary,
            meta={"change_kind": change_kind.value},
        )
        self._maybe_create_automatic_snapshot(user_id=user_id, space_id=space_id)

    @staticmethod
    def _fact_snapshot(item) -> dict:
        return {
            "id": item.id,
            "key": item.key,
            "value": item.value,
            "status": item.status.value,
            "source": item.source,
            "space_id": item.space_id,
        }

    @staticmethod
    def _rule_snapshot(item) -> dict:
        return {
            "id": item.id,
            "title": item.title,
            "instruction": item.instruction,
            "scope": item.scope.value,
            "strictness": item.strictness.value,
            "status": item.status.value,
            "source": item.source.value,
            "space_id": item.space_id,
        }

    @staticmethod
    def _personality_snapshot(item) -> dict:
        return {
            "id": item.id,
            "scope": item.scope.value,
            "space_id": item.space_id,
            "name": item.name,
            "tone": item.tone,
            "style_notes": item.style_notes,
            "humor_level": item.humor_level,
            "initiative_level": item.initiative_level,
            "can_gently_disagree": item.can_gently_disagree,
            "address_user_by_name": item.address_user_by_name,
            "is_active": item.is_active,
        }

    @staticmethod
    def _validate_personality_levels(*, humor_level: int, initiative_level: int) -> None:
        if humor_level < 0 or humor_level > 2:
            raise MemoryValidationError("humor_level должен быть в диапазоне 0..2.")
        if initiative_level < 0 or initiative_level > 2:
            raise MemoryValidationError("initiative_level должен быть в диапазоне 0..2.")

    def _build_snapshot_payload(self, *, user: User, space_id: str | None) -> dict:
        facts = self.list_facts(user=user, active_only=False)
        rules = self.list_rules(user=user, active_only=False)
        episodes = self.list_episodes(user=user, active_only=False)
        base = self._personality.get_base_for_user(user.id)
        spaces = self._spaces.list_spaces(user)
        settings_items = [
            self._session.get(SpaceMemorySettings, space.id)
            for space in spaces
        ]
        payload = {
            "facts": [self._fact_snapshot(item) for item in facts if self._in_space_scope(item.space_id, space_id)],
            "rules": [self._rule_snapshot(item) for item in rules if self._in_space_scope(item.space_id, space_id)],
            "episodes": [
                {
                    "id": item.id,
                    "chat_id": item.chat_id,
                    "summary": item.summary,
                    "status": item.status.value,
                    "source": item.source,
                    "space_id": item.space_id,
                }
                for item in episodes
                if self._in_space_scope(item.space_id, space_id)
            ],
            "personalities": [],
            "space_settings": [],
        }
        if base is not None:
            payload["personalities"].append(self._personality_snapshot(base))
        for space in spaces:
            overlay = self._personality.get_space_overlay_any_for_user(user_id=user.id, space_id=space.id)
            if overlay is not None and self._in_space_scope(overlay.space_id, space_id):
                payload["personalities"].append(self._personality_snapshot(overlay))
        for item in settings_items:
            if item is None:
                continue
            if not self._in_space_scope(item.space_id, space_id):
                continue
            payload["space_settings"].append(
                {
                    "space_id": item.space_id,
                    "memory_read_enabled": item.memory_read_enabled,
                    "memory_write_enabled": item.memory_write_enabled,
                    "behavior_rules_enabled": item.behavior_rules_enabled,
                    "personality_overlay_enabled": item.personality_overlay_enabled,
                }
            )
        return payload

    def _apply_facts_rollback(self, *, user_id: str, facts_payload) -> None:
        if not isinstance(facts_payload, list):
            return
        current = {item.id: item for item in self._facts.list_for_user(user_id, include_deleted=True)}
        payload_map = {item.get("id"): item for item in facts_payload if isinstance(item, dict) and isinstance(item.get("id"), str)}
        for fact_id, item in current.items():
            if fact_id in payload_map:
                data = payload_map[fact_id]
                if isinstance(data.get("key"), str):
                    item.key = data["key"]
                if isinstance(data.get("value"), str):
                    item.value = data["value"]
                if isinstance(data.get("source"), str):
                    item.source = data["source"]
                if isinstance(data.get("space_id"), str) or data.get("space_id") is None:
                    item.space_id = data.get("space_id")
                status_raw = data.get("status")
                if isinstance(status_raw, str):
                    try:
                        item.status = MemoryStatus(status_raw)
                    except ValueError:
                        pass
                self._facts.save(item)
            else:
                if item.status != MemoryStatus.DELETED:
                    item.status = MemoryStatus.DELETED
                    self._facts.save(item)

    def _apply_rules_rollback(self, *, user_id: str, rules_payload) -> None:
        if not isinstance(rules_payload, list):
            return
        current = {item.id: item for item in self._rules.list_for_user(user_id, active_only=False)}
        payload_map = {item.get("id"): item for item in rules_payload if isinstance(item, dict) and isinstance(item.get("id"), str)}
        for rule_id, item in current.items():
            if rule_id in payload_map:
                data = payload_map[rule_id]
                if isinstance(data.get("title"), str):
                    item.title = data["title"]
                if isinstance(data.get("instruction"), str):
                    item.instruction = data["instruction"]
                if isinstance(data.get("source"), str):
                    try:
                        item.source = RuleSource(data["source"])
                    except ValueError:
                        pass
                if isinstance(data.get("scope"), str):
                    try:
                        item.scope = RuleScope(data["scope"])
                    except ValueError:
                        pass
                if isinstance(data.get("strictness"), str):
                    try:
                        item.strictness = RuleStrictness(data["strictness"])
                    except ValueError:
                        pass
                if isinstance(data.get("status"), str):
                    try:
                        item.status = RuleStatus(data["status"])
                    except ValueError:
                        pass
                if isinstance(data.get("space_id"), str) or data.get("space_id") is None:
                    item.space_id = data.get("space_id")
                self._rules.save(item)
            else:
                if item.status != RuleStatus.ARCHIVED:
                    item.status = RuleStatus.ARCHIVED
                    self._rules.save(item)

    def _apply_personalities_rollback(self, *, user_id: str, profiles_payload) -> None:
        if not isinstance(profiles_payload, list):
            return
        valid_profiles = [item for item in profiles_payload if isinstance(item, dict)]
        for data in valid_profiles:
            scope_raw = data.get("scope")
            space_id = data.get("space_id")
            if not isinstance(scope_raw, str):
                continue
            try:
                scope = PersonalityScope(scope_raw)
            except ValueError:
                continue
            current = None
            if scope == PersonalityScope.BASE:
                current = self._personality.get_base_for_user(user_id)
            elif isinstance(space_id, str):
                current = self._personality.get_space_overlay_any_for_user(user_id=user_id, space_id=space_id)
            if current is None:
                current = AssistantPersonalityProfile(
                    user_id=user_id,
                    scope=scope,
                    space_id=(space_id if isinstance(space_id, str) else None),
                    name="Asya",
                    tone="balanced",
                    style_notes="",
                    humor_level=1,
                    initiative_level=1,
                    can_gently_disagree=True,
                    address_user_by_name=True,
                    is_active=True,
                )
            if isinstance(data.get("name"), str):
                current.name = data["name"]
            if isinstance(data.get("tone"), str):
                current.tone = data["tone"]
            if isinstance(data.get("style_notes"), str):
                current.style_notes = data["style_notes"]
            if isinstance(data.get("humor_level"), int):
                current.humor_level = data["humor_level"]
            if isinstance(data.get("initiative_level"), int):
                current.initiative_level = data["initiative_level"]
            if isinstance(data.get("can_gently_disagree"), bool):
                current.can_gently_disagree = data["can_gently_disagree"]
            if isinstance(data.get("address_user_by_name"), bool):
                current.address_user_by_name = data["address_user_by_name"]
            if isinstance(data.get("is_active"), bool):
                current.is_active = data["is_active"]
            self._personality.save(current)

    def _apply_space_settings_rollback(self, *, user: User, settings_payload) -> None:
        if not isinstance(settings_payload, list):
            return
        for data in settings_payload:
            if not isinstance(data, dict):
                continue
            space_id = data.get("space_id")
            if not isinstance(space_id, str):
                continue
            try:
                space = self._spaces.get_space_for_user(user=user, space_id=space_id)
            except SpaceNotFoundError:
                continue
            settings = self._session.get(SpaceMemorySettings, space.id)
            if settings is None:
                continue
            if isinstance(data.get("memory_read_enabled"), bool):
                settings.memory_read_enabled = data["memory_read_enabled"]
            if isinstance(data.get("memory_write_enabled"), bool):
                settings.memory_write_enabled = data["memory_write_enabled"]
            if isinstance(data.get("behavior_rules_enabled"), bool):
                settings.behavior_rules_enabled = data["behavior_rules_enabled"]
            if isinstance(data.get("personality_overlay_enabled"), bool):
                settings.personality_overlay_enabled = data["personality_overlay_enabled"]
            self._session.add(settings)

    def _apply_episodes_rollback(self, *, user_id: str, episodes_payload) -> None:
        if not isinstance(episodes_payload, list):
            return
        current = {item.id: item for item in self._episodes.list_for_user(user_id, active_only=False)}
        payload_map = {item.get("id"): item for item in episodes_payload if isinstance(item, dict) and isinstance(item.get("id"), str)}
        for episode_id, item in current.items():
            if episode_id in payload_map:
                data = payload_map[episode_id]
                if isinstance(data.get("summary"), str):
                    item.summary = data["summary"]
                if isinstance(data.get("source"), str):
                    item.source = data["source"]
                if isinstance(data.get("space_id"), str) or data.get("space_id") is None:
                    item.space_id = data.get("space_id")
                status_raw = data.get("status")
                if isinstance(status_raw, str):
                    try:
                        item.status = MemoryStatus(status_raw)
                    except ValueError:
                        pass
                self._session.add(item)
            else:
                if item.status != MemoryStatus.DELETED:
                    item.status = MemoryStatus.DELETED
                    self._session.add(item)

    def _maybe_create_automatic_snapshot(self, *, user_id: str, space_id: str | None) -> None:
        user = self._users.get_by_id(user_id)
        if user is None:
            return
        latest = self._snapshots.latest_for_user(user_id)
        now = datetime.now(timezone.utc)
        should_create = False
        label = ""
        if latest is None:
            should_create = True
            label = f"Auto weekly {now.isocalendar().year}-W{now.isocalendar().week:02d}"
        else:
            latest_at = latest.created_at
            if latest_at.tzinfo is None:
                latest_at = latest_at.replace(tzinfo=timezone.utc)
            latest_week = latest_at.isocalendar()
            current_week = now.isocalendar()
            if (latest_week.year, latest_week.week) != (current_week.year, current_week.week):
                should_create = True
                label = f"Auto weekly {current_week.year}-W{current_week.week:02d}"
            else:
                changes_since_latest = self._changes.count_for_user_since(user_id, date_from=latest_at)
                if changes_since_latest >= self.AUTO_SNAPSHOT_CHANGE_THRESHOLD:
                    should_create = True
                    label = f"Auto anomaly {now.strftime('%Y-%m-%d %H:%M')}"
        if not should_create:
            return
        payload = self._build_snapshot_payload(user=user, space_id=space_id)
        snapshot = self._snapshots.create(
            user_id=user.id,
            space_id=space_id,
            label=label,
            payload=payload,
        )
        self._activity.create(
            user_id=user.id,
            space_id=space_id,
            event_type=ActivityEventType.MEMORY_SNAPSHOT_CREATED,
            entity_type=ActivityEntityType.MEMORY_SNAPSHOT,
            entity_id=snapshot.id,
            summary=f"Автоматически создан snapshot памяти: {snapshot.label}",
            meta={"auto": True},
        )

    @staticmethod
    def _in_space_scope(item_space_id: str | None, space_id: str | None) -> bool:
        if space_id is None:
            return True
        return item_space_id is None or item_space_id == space_id
