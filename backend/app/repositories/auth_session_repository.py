from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.auth_session import AuthSession


class AuthSessionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, *, user_id: str, session_token_hash: str, expires_at: datetime) -> AuthSession:
        auth_session = AuthSession(
            user_id=user_id,
            session_token_hash=session_token_hash,
            expires_at=expires_at,
            revoked_at=None,
        )
        self._session.add(auth_session)
        self._session.flush()
        return auth_session

    def get_active_by_token_hash(self, token_hash: str, now: datetime) -> Optional[AuthSession]:
        stmt = select(AuthSession).where(
            AuthSession.session_token_hash == token_hash,
            AuthSession.revoked_at.is_(None),
            AuthSession.expires_at > now,
        )
        return self._session.execute(stmt).scalar_one_or_none()

    def revoke(self, auth_session: AuthSession, revoked_at: datetime) -> None:
        auth_session.revoked_at = revoked_at
        self._session.add(auth_session)
        self._session.flush()
