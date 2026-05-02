from __future__ import annotations

from abc import ABC
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from urllib.parse import urlencode

import httpx
from sqlalchemy.orm import Session

from app.db.models.common import IntegrationConnectionStatus, IntegrationProvider
from app.integrations.oauth_state import OAuthState, OAuthStateService
from app.services.encrypted_secret_service import EncryptedSecretService, SecretNotFoundError
from app.services.integration_connection_service import IntegrationConnectionService, IntegrationConnectionUpsertPayload
from app.services.secret_crypto_service import SecretCryptoService
from app.core.config import get_settings


class OAuthProviderError(RuntimeError):
    pass


class OAuthRefreshTokenExpiredError(OAuthProviderError):
    pass


@dataclass
class OAuthProviderConfig:
    provider: IntegrationProvider
    client_id: str
    client_secret: str
    authorize_url: str
    token_url: str
    revoke_url: Optional[str]
    supports_pkce: bool = True


@dataclass
class OAuthTokens:
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "Bearer"
    expires_in: Optional[int] = None
    scope: Optional[str] = None


@dataclass
class AuthenticatedOAuthClient:
    provider: IntegrationProvider
    access_token: str
    token_type: str

    @property
    def authorization_header(self) -> str:
        return f"{self.token_type} {self.access_token}".strip()


class OAuthIntegration(ABC):
    def __init__(self, session: Session, config: OAuthProviderConfig) -> None:
        self._session = session
        self._config = config
        self._state_service = OAuthStateService(session)
        self._connections = IntegrationConnectionService(session)
        self._secrets = EncryptedSecretService(
            session,
            SecretCryptoService(get_settings().master_encryption_key),
        )

    def authorization_url(self, user_id: str, redirect_uri: str, scopes: list[str]) -> str:
        state = self._state_service.create(
            user_id=user_id,
            provider=self._config.provider,
            redirect_uri=redirect_uri,
            scopes=scopes,
        )
        params = {
            "response_type": "code",
            "client_id": self._config.client_id,
            "redirect_uri": redirect_uri,
            "scope": " ".join(scopes),
            "state": state.state_token,
        }
        if self._config.supports_pkce:
            params["code_challenge"] = state.code_challenge
            params["code_challenge_method"] = "S256"
        return f"{self._config.authorize_url}?{urlencode(params)}"

    def exchange_code(self, code: str, state: OAuthState) -> OAuthTokens:
        payload: dict[str, Any] = {
            "grant_type": "authorization_code",
            "code": code,
            "client_id": self._config.client_id,
            "redirect_uri": state.redirect_uri,
        }
        if self._config.client_secret:
            payload["client_secret"] = self._config.client_secret
        if self._config.supports_pkce:
            payload["code_verifier"] = state.code_verifier

        tokens = self._post_tokens(payload)
        expires_at = self._now() + timedelta(seconds=tokens.expires_in or 3600)
        self._connections.upsert_connection_by_user_id(
            user_id=state.user_id,
            payload=IntegrationConnectionUpsertPayload(
                provider=self._config.provider,
                status=IntegrationConnectionStatus.CONNECTED,
                scopes=state.scopes,
                connected_at=self._now(),
                last_refresh_at=self._now(),
                safe_error_metadata=None,
                access_token=tokens.access_token,
                refresh_token=tokens.refresh_token,
            ),
        )
        self._connections.mark_synced_by_user_id(
            user_id=state.user_id,
            provider=self._config.provider,
            at=expires_at,
        )
        return tokens

    def refresh_access_token(self, refresh_token: str) -> OAuthTokens:
        payload: dict[str, Any] = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": self._config.client_id,
        }
        if self._config.client_secret:
            payload["client_secret"] = self._config.client_secret
        return self._post_tokens(payload)

    def revoke(self, token: str) -> None:
        if not self._config.revoke_url:
            return
        try:
            response = httpx.post(self._config.revoke_url, data={"token": token}, timeout=20.0)
            if response.status_code >= 400:
                raise OAuthProviderError(f"Не удалось отозвать токен: {response.status_code}.")
        except httpx.HTTPError as exc:
            raise OAuthProviderError("Ошибка сети при revoke токена.") from exc

    def get_authenticated_client(self, user_id: str) -> AuthenticatedOAuthClient:
        access_name = self._secret_name("access_token")
        token = self._secrets.get_secret(user_id=user_id, name=access_name)
        return AuthenticatedOAuthClient(
            provider=self._config.provider,
            access_token=token,
            token_type="Bearer",
        )

    def consume_state(self, user_id: str, state_token: str) -> OAuthState:
        return self._state_service.consume(
            user_id=user_id,
            provider=self._config.provider,
            state_token=state_token,
        )

    def _post_tokens(self, payload: dict[str, Any]) -> OAuthTokens:
        try:
            response = httpx.post(self._config.token_url, data=payload, timeout=20.0)
        except httpx.HTTPError as exc:
            raise OAuthProviderError("Сетевая ошибка провайдера при обмене OAuth-кода.") from exc

        if response.status_code >= 400:
            text = response.text[:500]
            if "invalid_grant" in text.lower():
                raise OAuthRefreshTokenExpiredError("Refresh token истёк или отозван.")
            raise OAuthProviderError(f"Ошибка OAuth провайдера: {response.status_code}.")

        data = response.json()
        access_token = str(data.get("access_token", "")).strip()
        if not access_token:
            raise OAuthProviderError("Провайдер не вернул access_token.")
        refresh_token_raw = data.get("refresh_token")
        refresh_token = str(refresh_token_raw).strip() if refresh_token_raw else None
        return OAuthTokens(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type=str(data.get("token_type", "Bearer")),
            expires_in=int(data["expires_in"]) if data.get("expires_in") is not None else None,
            scope=data.get("scope"),
        )

    def load_refresh_token(self, user_id: str) -> str:
        try:
            return self._secrets.get_secret(user_id=user_id, name=self._secret_name("refresh_token"))
        except SecretNotFoundError as exc:
            raise OAuthProviderError("Refresh token не найден.") from exc

    def _secret_name(self, token_type: str) -> str:
        return f"integration:{self._config.provider.value}:{token_type}"

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)
