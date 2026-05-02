from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.common import IntegrationProvider
from app.db.models.oauth_state import OAuthState


class OAuthStateRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(
        self,
        *,
        user_id: str,
        provider: IntegrationProvider,
        state_token: str,
        code_verifier: str,
        redirect_uri: str,
        scopes: list[str],
        expires_at: datetime,
    ) -> OAuthState:
        item = OAuthState(
            user_id=user_id,
            provider=provider,
            state_token=state_token,
            code_verifier=code_verifier,
            redirect_uri=redirect_uri,
            scopes=scopes,
            expires_at=expires_at,
            used_at=None,
            safe_error_metadata=None,
        )
        self._session.add(item)
        self._session.flush()
        return item

    def get_by_state_token(self, *, state_token: str) -> OAuthState | None:
        stmt = select(OAuthState).where(OAuthState.state_token == state_token)
        return self._session.execute(stmt).scalar_one_or_none()

    def save(self, item: OAuthState) -> OAuthState:
        self._session.add(item)
        self._session.flush()
        return item
