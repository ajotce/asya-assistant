from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models.common import IntegrationProvider
from app.integrations.oauth_base import OAuthIntegration, OAuthProviderConfig


class GoogleOAuthIntegration(OAuthIntegration):
    def __init__(self, session: Session) -> None:
        settings = get_settings()
        super().__init__(
            session,
            OAuthProviderConfig(
                provider=IntegrationProvider.GOOGLE_CALENDAR,
                client_id=settings.google_oauth_client_id,
                client_secret=settings.google_oauth_client_secret,
                authorize_url=settings.google_oauth_authorize_url,
                token_url=settings.google_oauth_token_url,
                revoke_url=settings.google_oauth_revoke_url,
                supports_pkce=True,
            ),
        )
