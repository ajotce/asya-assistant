from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.signup_token import SignupToken


class SignupTokenRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(
        self,
        *,
        access_request_id: str | None,
        user_id: str | None,
        email: str,
        token_hash: str,
        created_by_user_id: str | None,
        expires_at: datetime,
    ) -> SignupToken:
        token = SignupToken(
            access_request_id=access_request_id,
            user_id=user_id,
            email=email,
            token_hash=token_hash,
            created_by_user_id=created_by_user_id,
            expires_at=expires_at,
            used_at=None,
        )
        self._session.add(token)
        self._session.flush()
        return token

    def get_active_by_hash(self, token_hash: str, *, now: datetime) -> SignupToken | None:
        stmt = select(SignupToken).where(
            SignupToken.token_hash == token_hash,
            SignupToken.used_at.is_(None),
            SignupToken.expires_at > now,
        )
        return self._session.execute(stmt).scalar_one_or_none()

    def save(self, token: SignupToken) -> SignupToken:
        self._session.add(token)
        self._session.flush()
        return token
