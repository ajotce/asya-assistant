from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models.common import IntegrationProvider
from app.integrations.oauth_base import OAuthIntegration
from app.integrations.providers.google_oauth import GoogleOAuthIntegration
from app.integrations.providers.linear_oauth import LinearOAuthIntegration
from app.integrations.providers.todoist_oauth import TodoistOAuthIntegration


def build_oauth_integration(session: Session, provider: IntegrationProvider) -> OAuthIntegration:
    if provider == IntegrationProvider.LINEAR:
        return LinearOAuthIntegration(session)
    if provider == IntegrationProvider.GOOGLE_CALENDAR:
        return GoogleOAuthIntegration(session)
    if provider == IntegrationProvider.TODOIST:
        return TodoistOAuthIntegration(session)
    raise ValueError("OAuth provider not supported in this phase.")
