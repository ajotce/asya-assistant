from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.space import Space


class SpaceRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_for_user(self, user_id: str, *, include_archived: bool = False) -> list[Space]:
        stmt = select(Space).where(Space.user_id == user_id)
        if not include_archived:
            stmt = stmt.where(Space.is_archived.is_(False))
        stmt = stmt.order_by(Space.created_at.asc())
        return list(self._session.execute(stmt).scalars())

    def get_for_user(self, space_id: str, user_id: str) -> Optional[Space]:
        stmt = select(Space).where(Space.id == space_id, Space.user_id == user_id)
        return self._session.execute(stmt).scalar_one_or_none()

    def get_by_name_for_user(self, *, user_id: str, name: str) -> Optional[Space]:
        stmt = select(Space).where(Space.user_id == user_id, Space.name == name)
        return self._session.execute(stmt).scalar_one_or_none()

    def get_default_for_user(self, user_id: str) -> Optional[Space]:
        stmt = (
            select(Space)
            .where(
                Space.user_id == user_id,
                Space.is_default.is_(True),
                Space.is_archived.is_(False),
            )
            .order_by(Space.created_at.asc())
        )
        return self._session.execute(stmt).scalar_one_or_none()

    def get_admin_dev_for_user(self, user_id: str) -> Optional[Space]:
        stmt = (
            select(Space)
            .where(
                Space.user_id == user_id,
                Space.is_admin_only.is_(True),
                Space.name == "Asya-dev",
            )
            .order_by(Space.created_at.asc())
        )
        return self._session.execute(stmt).scalar_one_or_none()

    def create(
        self,
        *,
        user_id: str,
        name: str,
        is_default: bool = False,
        is_archived: bool = False,
        is_admin_only: bool = False,
    ) -> Space:
        space = Space(
            user_id=user_id,
            name=name,
            is_default=is_default,
            is_archived=is_archived,
            is_admin_only=is_admin_only,
        )
        self._session.add(space)
        self._session.flush()
        return space

    def save(self, space: Space) -> Space:
        self._session.add(space)
        self._session.flush()
        return space
