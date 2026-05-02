from __future__ import annotations

from datetime import timedelta, timezone, datetime
from urllib.parse import parse_qs, urlparse

import pytest
from sqlalchemy.orm import Session

from app.db.models.common import IntegrationProvider, UserStatus
from app.db.models.oauth_state import OAuthState as OAuthStateModel
from app.integrations.oauth_service import OAuthIntegrationService
from app.integrations.oauth_state import (
    OAuthStateExpiredError,
    OAuthStateInvalidError,
    OAuthStateOwnershipError,
    OAuthStateReusedError,
)
from app.integrations.providers.mock_oauth import MockOAuthIntegration
from app.repositories.encrypted_secret_repository import EncryptedSecretRepository
from app.repositories.user_repository import UserRepository
from tests.auth_helpers import setup_test_db


def _create_user(session: Session, *, email: str, display_name: str):
    user = UserRepository(session).create(
        email=email,
        display_name=display_name,
        password_hash="hash",
        status=UserStatus.ACTIVE,
    )
    session.commit()
    return user


def _mock_factory(session: Session, provider: IntegrationProvider):
    return MockOAuthIntegration(session, provider=provider)


def test_mock_oauth_flow_exchanges_code_and_stores_tokens_encrypted(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("MASTER_ENCRYPTION_KEY", "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY=")
    monkeypatch.setenv("OAUTH_STATE_TTL_SECONDS", "900")
    _, engine = setup_test_db(tmp_path, monkeypatch)
    monkeypatch.setattr("app.integrations.oauth_service.build_oauth_integration", _mock_factory)

    with Session(bind=engine) as session:
        user = _create_user(session, email="oauth-user@example.com", display_name="OAuth User")
        service = OAuthIntegrationService(session)

        url = service.authorization_url(
            provider=IntegrationProvider.LINEAR,
            user_id=user.id,
            redirect_uri="http://localhost:8000/api/integrations/linear/callback",
            scopes=["read", "write"],
        )
        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        state_token = query["state"][0]

        tokens = service.exchange_code(
            provider=IntegrationProvider.LINEAR,
            user_id=user.id,
            code="mock-auth-code",
            state=state_token,
        )
        assert tokens.access_token == "mock-access-token"
        assert tokens.refresh_token == "mock-refresh-token"
        client = service.get_authenticated_client(provider=IntegrationProvider.LINEAR, user_id=user.id)
        assert client.authorization_header == "Bearer mock-access-token"

        secret_repo = EncryptedSecretRepository(session)
        access_item = secret_repo.get_by_user_and_name(
            user_id=user.id,
            name="integration:linear:access_token",
        )
        refresh_item = secret_repo.get_by_user_and_name(
            user_id=user.id,
            name="integration:linear:refresh_token",
        )
        assert access_item is not None
        assert refresh_item is not None
        assert access_item.encrypted_value != b"mock-access-token"
        assert refresh_item.encrypted_value != b"mock-refresh-token"


def test_oauth_state_one_time_use_and_user_scoped(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("MASTER_ENCRYPTION_KEY", "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY=")
    _, engine = setup_test_db(tmp_path, monkeypatch)
    monkeypatch.setattr("app.integrations.oauth_service.build_oauth_integration", _mock_factory)

    with Session(bind=engine) as session:
        user_a = _create_user(session, email="oauth-a@example.com", display_name="A")
        user_b = _create_user(session, email="oauth-b@example.com", display_name="B")
        service = OAuthIntegrationService(session)

        url = service.authorization_url(
            provider=IntegrationProvider.TODOIST,
            user_id=user_a.id,
            redirect_uri="http://localhost/callback",
            scopes=["tasks:read"],
        )
        state_token = parse_qs(urlparse(url).query)["state"][0]

        with pytest.raises(OAuthStateInvalidError):
            service.exchange_code(
                provider=IntegrationProvider.TODOIST,
                user_id=user_a.id,
                code="ok",
                state="invalid-state-token",
            )

        with pytest.raises(OAuthStateOwnershipError):
            service.exchange_code(
                provider=IntegrationProvider.TODOIST,
                user_id=user_b.id,
                code="ok",
                state=state_token,
            )

        service.exchange_code(
            provider=IntegrationProvider.TODOIST,
            user_id=user_a.id,
            code="ok",
            state=state_token,
        )
        with pytest.raises(OAuthStateReusedError):
            service.exchange_code(
                provider=IntegrationProvider.TODOIST,
                user_id=user_a.id,
                code="ok-again",
                state=state_token,
            )


def test_oauth_state_expired(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("MASTER_ENCRYPTION_KEY", "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY=")
    _, engine = setup_test_db(tmp_path, monkeypatch)
    monkeypatch.setattr("app.integrations.oauth_service.build_oauth_integration", _mock_factory)

    with Session(bind=engine) as session:
        user = _create_user(session, email="oauth-exp@example.com", display_name="Exp")
        service = OAuthIntegrationService(session)

        url = service.authorization_url(
            provider=IntegrationProvider.GOOGLE_CALENDAR,
            user_id=user.id,
            redirect_uri="http://localhost/google-callback",
            scopes=["calendar.readonly"],
        )
        state_token = parse_qs(urlparse(url).query)["state"][0]
        state_row = session.query(OAuthStateModel).filter_by(state_token=state_token).one()
        state_row.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        session.add(state_row)
        session.commit()

        with pytest.raises(OAuthStateExpiredError):
            service.exchange_code(
                provider=IntegrationProvider.GOOGLE_CALENDAR,
                user_id=user.id,
                code="expired",
                state=state_token,
            )
