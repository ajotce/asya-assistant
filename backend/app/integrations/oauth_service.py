from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models.common import IntegrationConnectionStatus, IntegrationProvider
from app.integrations.oauth_base import (
    AuthenticatedOAuthClient,
    OAuthProviderError,
    OAuthRefreshTokenExpiredError,
    OAuthTokens,
)
from app.integrations.providers import build_oauth_integration
from app.services.integration_connection_service import IntegrationConnectionService, IntegrationConnectionUpsertPayload


class OAuthIntegrationService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._connections = IntegrationConnectionService(session)

    def authorization_url(
        self,
        *,
        provider: IntegrationProvider,
        user_id: str,
        redirect_uri: str,
        scopes: list[str],
    ) -> str:
        integration = build_oauth_integration(self._session, provider)
        return integration.authorization_url(user_id=user_id, redirect_uri=redirect_uri, scopes=scopes)

    def exchange_code(
        self,
        *,
        provider: IntegrationProvider,
        user_id: str,
        code: str,
        state: str,
    ) -> OAuthTokens:
        integration = build_oauth_integration(self._session, provider)
        consumed = integration.consume_state(user_id=user_id, state_token=state)
        try:
            return integration.exchange_code(code=code, state=consumed)
        except OAuthProviderError:
            self._connections.upsert_connection_by_user_id(
                user_id=user_id,
                payload=IntegrationConnectionUpsertPayload(
                    provider=provider,
                    status=IntegrationConnectionStatus.ERROR,
                    scopes=consumed.scopes,
                    safe_error_metadata={"stage": "exchange_code"},
                ),
            )
            raise

    def refresh_access_token(
        self,
        *,
        provider: IntegrationProvider,
        user_id: str,
    ) -> OAuthTokens:
        integration = build_oauth_integration(self._session, provider)
        refresh_token = integration.load_refresh_token(user_id=user_id)
        try:
            tokens = integration.refresh_access_token(refresh_token=refresh_token)
        except OAuthRefreshTokenExpiredError:
            self._connections.upsert_connection_by_user_id(
                user_id=user_id,
                payload=IntegrationConnectionUpsertPayload(
                    provider=provider,
                    status=IntegrationConnectionStatus.EXPIRED,
                    scopes=[],
                    safe_error_metadata={"stage": "refresh_access_token"},
                ),
            )
            raise
        except OAuthProviderError:
            self._connections.upsert_connection_by_user_id(
                user_id=user_id,
                payload=IntegrationConnectionUpsertPayload(
                    provider=provider,
                    status=IntegrationConnectionStatus.ERROR,
                    scopes=[],
                    safe_error_metadata={"stage": "refresh_access_token"},
                ),
            )
            raise

        self._connections.upsert_connection_by_user_id(
            user_id=user_id,
            payload=IntegrationConnectionUpsertPayload(
                provider=provider,
                status=IntegrationConnectionStatus.CONNECTED,
                scopes=[],
                last_refresh_at=IntegrationConnectionService._now(),
                access_token=tokens.access_token,
                refresh_token=tokens.refresh_token or refresh_token,
                safe_error_metadata=None,
            ),
        )
        return tokens

    def revoke(
        self,
        *,
        provider: IntegrationProvider,
        user_id: str,
    ) -> None:
        integration = build_oauth_integration(self._session, provider)
        client = integration.get_authenticated_client(user_id=user_id)
        integration.revoke(client.access_token)

    def get_authenticated_client(
        self,
        *,
        provider: IntegrationProvider,
        user_id: str,
    ) -> AuthenticatedOAuthClient:
        integration = build_oauth_integration(self._session, provider)
        return integration.get_authenticated_client(user_id=user_id)
