from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models.common import IntegrationProvider
from app.integrations.oauth_base import OAuthIntegration, OAuthProviderConfig


class GitHubOAuthIntegration(OAuthIntegration):
    def __init__(self, session: Session) -> None:
        settings = get_settings()
        super().__init__(
            session,
            OAuthProviderConfig(
                provider=IntegrationProvider.GITHUB,
                client_id=settings.github_oauth_client_id,
                client_secret=settings.github_oauth_client_secret,
                authorize_url=settings.github_oauth_authorize_url,
                token_url=settings.github_oauth_token_url,
                revoke_url=settings.github_oauth_revoke_url or None,
                supports_pkce=True,
            ),
        )
