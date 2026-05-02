from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.assistant_personality_profile import AssistantPersonalityProfile
from app.db.models.common import PersonalityScope


class PersonalityProfileRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_base_for_user(self, user_id: str) -> AssistantPersonalityProfile | None:
        stmt = select(AssistantPersonalityProfile).where(
            AssistantPersonalityProfile.user_id == user_id,
            AssistantPersonalityProfile.scope == PersonalityScope.BASE,
            AssistantPersonalityProfile.space_id.is_(None),
        )
        return self._session.execute(stmt).scalar_one_or_none()

    def get_space_overlay_for_user(self, *, user_id: str, space_id: str) -> AssistantPersonalityProfile | None:
        stmt = select(AssistantPersonalityProfile).where(
            AssistantPersonalityProfile.user_id == user_id,
            AssistantPersonalityProfile.scope == PersonalityScope.SPACE_OVERLAY,
            AssistantPersonalityProfile.space_id == space_id,
            AssistantPersonalityProfile.is_active.is_(True),
        )
        return self._session.execute(stmt).scalar_one_or_none()

    def get_space_overlay_any_for_user(self, *, user_id: str, space_id: str) -> AssistantPersonalityProfile | None:
        stmt = select(AssistantPersonalityProfile).where(
            AssistantPersonalityProfile.user_id == user_id,
            AssistantPersonalityProfile.scope == PersonalityScope.SPACE_OVERLAY,
            AssistantPersonalityProfile.space_id == space_id,
        )
        return self._session.execute(stmt).scalar_one_or_none()

    def save(self, item: AssistantPersonalityProfile) -> AssistantPersonalityProfile:
        self._session.add(item)
        self._session.flush()
        return item
