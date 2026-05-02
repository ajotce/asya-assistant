from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models.common import IntegrationProvider
from app.integrations.oauth_base import OAuthIntegration, OAuthProviderConfig


class LinearOAuthIntegration(OAuthIntegration):
    def __init__(self, session: Session) -> None:
        settings = get_settings()
        super().__init__(
            session,
            OAuthProviderConfig(
                provider=IntegrationProvider.LINEAR,
                client_id=settings.linear_oauth_client_id,
                client_secret=settings.linear_oauth_client_secret,
                authorize_url=settings.linear_oauth_authorize_url,
                token_url=settings.linear_oauth_token_url,
                revoke_url=settings.linear_oauth_revoke_url,
                supports_pkce=True,
            ),
        )
