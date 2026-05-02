from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models.common import IntegrationProvider
from app.integrations.oauth_base import OAuthIntegration, OAuthProviderConfig, OAuthTokens


class MockOAuthIntegration(OAuthIntegration):
    def __init__(self, session: Session, provider: IntegrationProvider = IntegrationProvider.LINEAR) -> None:
        super().__init__(
            session,
            OAuthProviderConfig(
                provider=provider,
                client_id="mock-client-id",
                client_secret="mock-client-secret",
                authorize_url="https://mock.example.test/oauth/authorize",
                token_url="https://mock.example.test/oauth/token",
                revoke_url="https://mock.example.test/oauth/revoke",
                supports_pkce=True,
            ),
        )

    def _post_tokens(self, payload: dict[str, object]) -> OAuthTokens:
        grant_type = str(payload.get("grant_type", ""))
        if grant_type == "authorization_code":
            return OAuthTokens(
                access_token="mock-access-token",
                refresh_token="mock-refresh-token",
                token_type="Bearer",
                expires_in=3600,
                scope=" ".join(str(payload.get("scope", "")).split()),
            )
        if grant_type == "refresh_token":
            return OAuthTokens(
                access_token="mock-access-token-refreshed",
                refresh_token="mock-refresh-token-next",
                token_type="Bearer",
                expires_in=3600,
            )
        raise RuntimeError("Unsupported grant type in mock provider.")
