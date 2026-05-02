from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import base64
import hashlib
import secrets

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models.common import IntegrationProvider
from app.db.models.oauth_state import OAuthState as OAuthStateModel
from app.repositories.oauth_state_repository import OAuthStateRepository


class OAuthStateError(ValueError):
    pass


class OAuthStateInvalidError(OAuthStateError):
    pass


class OAuthStateExpiredError(OAuthStateError):
    pass


class OAuthStateReusedError(OAuthStateError):
    pass


class OAuthStateOwnershipError(OAuthStateError):
    pass


@dataclass
class OAuthState:
    state_token: str
    code_verifier: str
    code_challenge: str
    provider: IntegrationProvider
    user_id: str
    redirect_uri: str
    scopes: list[str]
    expires_at: datetime


def generate_code_verifier() -> str:
    raw = secrets.token_urlsafe(96)
    verifier = raw[:128]
    if len(verifier) < 43:
        verifier = verifier + ("x" * (43 - len(verifier)))
    return verifier


def build_code_challenge(code_verifier: str) -> str:
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


class OAuthStateService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._repo = OAuthStateRepository(session)
        self._settings = get_settings()

    def create(
        self,
        *,
        user_id: str,
        provider: IntegrationProvider,
        redirect_uri: str,
        scopes: list[str],
    ) -> OAuthState:
        state_token = secrets.token_urlsafe(48)
        code_verifier = generate_code_verifier()
        code_challenge = build_code_challenge(code_verifier)
        expires_at = self._now() + timedelta(seconds=self._settings.oauth_state_ttl_seconds)
        self._repo.create(
            user_id=user_id,
            provider=provider,
            state_token=state_token,
            code_verifier=code_verifier,
            redirect_uri=redirect_uri,
            scopes=scopes,
            expires_at=expires_at,
        )
        self._session.commit()
        return OAuthState(
            state_token=state_token,
            code_verifier=code_verifier,
            code_challenge=code_challenge,
            provider=provider,
            user_id=user_id,
            redirect_uri=redirect_uri,
            scopes=scopes,
            expires_at=expires_at,
        )

    def consume(
        self,
        *,
        user_id: str,
        provider: IntegrationProvider,
        state_token: str,
    ) -> OAuthState:
        item = self._repo.get_by_state_token(state_token=state_token)
        if item is None:
            raise OAuthStateInvalidError("OAuth state не найден.")
        self._validate_before_consume(item=item, user_id=user_id, provider=provider)
        item.used_at = self._now()
        self._repo.save(item)
        self._session.commit()
        return OAuthState(
            state_token=item.state_token,
            code_verifier=item.code_verifier,
            code_challenge=build_code_challenge(item.code_verifier),
            provider=item.provider,
            user_id=item.user_id,
            redirect_uri=item.redirect_uri,
            scopes=item.scopes or [],
            expires_at=item.expires_at,
        )

    def _validate_before_consume(self, *, item: OAuthStateModel, user_id: str, provider: IntegrationProvider) -> None:
        if item.provider != provider or item.user_id != user_id:
            raise OAuthStateOwnershipError("OAuth state не принадлежит текущему пользователю или провайдеру.")
        if item.used_at is not None:
            raise OAuthStateReusedError("OAuth state уже был использован.")
        if self._as_aware_utc(item.expires_at) <= self._now():
            raise OAuthStateExpiredError("OAuth state истёк.")

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _as_aware_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
